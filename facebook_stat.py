# Copyright 2014 Facebook, Inc.

# You are hereby granted a non-exclusive, worldwide, royalty-free license to
# use, copy, modify, and distribute this software in source code or binary
# form for use in connection with the web services and APIs provided by
# Facebook.

# As with any software that integrates with the Facebook platform, your use
# of this software is subject to the Facebook Developer Principles and
# Policies [http://developers.facebook.com/policy/]. This copyright notice
# shall be included in all copies or substantial portions of the software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.


from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adsinsights import AdsInsights
import re


from core.models import Product, CartItem, PaymentCancel, AnalyticsCachePageviewMenuDetail, CartItemStatusLog
from analysis.spreadsheet.write_sheet import performance_monitoring_write
import redis
from datetime import timedelta


def nested_finder(diction, key):
    if isinstance(diction, dict):
        if diction.has_key(key):
            return diction.get(key)
        else:
            for k, v in diction.iteritems():
                return nested_finder(v, key)
    elif hasattr(diction, '_data'):
        return nested_finder(diction._data, key)
    else:
        return None


def get_current_pv(conn, product_id, day):
    pv = conn.get('day_view_count_furniture_{0}_{1}'.format(product_id, day))
    if pv is None:
        return 0
    return pv

# redis connect => 현재 pv를 가져오기 위해...
conn = redis.StrictRedis(host='...', port=..., db=...)


def get_facebook_ads_results(target_date, now_date, period):
    ad_account_ids = ['act_...', 'act_...']

    ''' regular expression for product id '''
    re_product_id = re.compile('[0-9]{4,}')

    results = {}

    app_secret = '...'
    app_id = '...'

    access_token = "..."

    FacebookAdsApi.init(access_token=access_token)

    start_date = str(target_date.date())
    end_date = str((now_date-timedelta(hours=5)).date())

    product_ids = []
    for ad_account_id in ad_account_ids:
        '''access_token has expire date.
         have to change it periodically'''

        ins_fields =[
            AdsInsights.Field.ad_id,
            AdsInsights.Field.ad_name,
            AdsInsights.Field.outbound_clicks,
            AdsInsights.Field.impressions,
            AdsInsights.Field.spend,
        ]

        ins_param = {
            'level': 'ad',
            'time_range': {'since': start_date, 'until': end_date},
            'action_attribution_windows': ['1d_click']
        }

        adins = AdAccount(ad_account_id).get_insights(
            fields=ins_fields,
            params=ins_param,
        )
        for ins in adins:
            match = re_product_id.match(ins._data['ad_name'])
            if match is None:
                continue
            match_product_id = int(match.group(0))

            if results.get(match_product_id) is None:
                results[match_product_id] = {}
                results[match_product_id]['id'] = match_product_id
                results[match_product_id]['clicks'] = 0
                results[match_product_id]['impressions'] = 0
                results[match_product_id]['spend'] = 0
            try:
                results[match_product_id]['clicks'] += int((ins._data[AdsInsights.Field.outbound_clicks])[0]['1d_click'])
            except:
                pass
            results[match_product_id]['impressions'] += int(ins._data[AdsInsights.Field.impressions])
            results[match_product_id]['spend'] += int(ins._data[AdsInsights.Field.spend])

            product_ids.append(match_product_id)

    products = Product.objects.filter(id__in=product_ids).prefetch_related('detail', 'brand', 'skus')
    for product in products:
        results[product.id]['name'] = product.name
        results[product.id]['brand'] = product.brand.name
        results[product.id]['total_count'] = 0
        results[product.id]['total_price'] = 0
        results[product.id]['daily_view'] = 0
        try:
            results[product.id]['commission'] = product.detail.commission
        except:
            results[product.id]['commission'] = 0

        if results[product.id]['commission'] == 0:
            try:
                results[product.id]['commission'] = product.skus.filter(status='A').last().commission
            except:
                pass

    # 결제기준
    order_cart_item_list = CartItemStatusLog.objects.filter(create_date_time__gte=target_date,
                                                            create_date_time__lt=now_date,
                                                            status=2, cart_item__product__id__in=product_ids)\
                                                            .values_list('cart_item', flat=True)

    order_cart_items = CartItem.objects.filter(id__in=order_cart_item_list).prefetch_related('product', 'order')

    for cart_item in order_cart_items:
        # 메인 상품일때
        if cart_item.parent_unit_idx == 0:
            # 상품 종류 개수 counting
            if results[cart_item.product_id].get('total_count') is None:
                results[cart_item.product_id]['total_price'] = 0
                results[cart_item.product_id]['total_count'] = 0
            results[cart_item.product_id]['total_price'] += cart_item.count * cart_item.price
            results[cart_item.product_id]['total_count'] += cart_item.count

    # 환불일 기준
    payment_cancels = PaymentCancel.objects.filter(created_date_time__gte=target_date, created_date_time__lt=now_date)

    cancel_group_ids = payment_cancels.values_list('delivery_group', flat=True).distinct()
    cancel_cart_items = CartItem.objects.filter(
        order__in=cancel_group_ids, status__in=[8, 10], product__id__in=product_ids)\
        .prefetch_related('product', 'order')

    for cart_item in cancel_cart_items:
        if cart_item.parent_unit_idx == 0:
            if results[cart_item.product_id].get('total_count') is None:
                results[cart_item.product_id]['total_price'] = 0
                results[cart_item.product_id]['total_count'] = 0
            results[cart_item.product_id]['total_price'] -= cart_item.count * cart_item.price
            results[cart_item.product_id]['total_count'] -= cart_item.count

    if target_date+timedelta(days=1) <= now_date:
        pageviews = AnalyticsCachePageviewMenuDetail.objects.filter(theday__gte=target_date, theday__lt=now_date,
                                                                    type='furniture', type_idx__in=product_ids).order_by('type_idx')
        for pageview in pageviews:
            if results[pageview.type_idx].get('daily_view') is None:
                results[pageview.type_idx]['daily_view'] = 0
            results[pageview.type_idx]['daily_view'] += pageview.total_count

    else:
        for id in results:
            results[id]['daily_view'] = int(get_current_pv(conn, id, start_date))

    performance_monitoring_write(results, target_date, now_date, period)
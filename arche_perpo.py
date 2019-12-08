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
from core.models import ProductOption, SKUOption, SKU
from analysis.spreadsheet.write_sheet import arche_perpo_write

from datetime import timedelta


def get_sku_name():
    dict_option = {}

    options = ProductOption.objects.filter()
    for option in options:
        dict_option[option.id] = option.name

    dict_sku = {}

    sku_options = SKUOption.objects.filter().prefetch_related('option_parent', 'option', 'sku')

    for sku_option in sku_options:
        if sku_option.option_parent is None:
            continue

        if dict_sku.get(sku_option.sku_id) is None:
            dict_sku[sku_option.sku_id] = dict_option[sku_option.option_id]
            dict_sku[sku_option.sku_id] = dict_sku[sku_option.sku_id] + ', ' + dict_option[sku_option.option_id]

    return dict_sku


def get_sku_extra_name():
    skus = SKU.objects.prefetch_related('sku_extra').filter(sku_extra__isnull=False)

    dict = {}
    for sku in skus:
        dict[sku.id] = sku.sku_extra.name

    return dict


def get_sku_code():
    skus = SKU.objects.filter(product__brand__name="...").prefetch_related('sku_extra')
    dict = {}
    for sku in skus:
        try:
            dict[sku.id] = sku.sku_extra.product_code
        except:
            dict[sku.id] = sku.product_code

    return dict


def get_default_dict(code, sku_name, is_extra, product_name, product_id, commission):
    dict = {}
    dict['code'] = code
    dict['sku_name'] = sku_name
    dict['product_name'] = product_name
    dict['is_extra'] = is_extra
    dict['product_id'] = product_id
    dict['commission'] = commission
    dict['total_price'] = 0
    dict['total_count'] = 0
    dict['daily_view'] = 0
    return dict


def get_arche_stat_results(target_date, now_date):
    ad_account_ids = ['act_...', 'act_...']

    ''' regular expression for product id '''
    re_product_id = re.compile('[0-9]{4,}')

    facebook_info = {}

    access_token = "..." # 비~밀

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

            if facebook_info.get(match_product_id) is None:
                facebook_info[match_product_id] = {}
                facebook_info[match_product_id]['id'] = match_product_id
                facebook_info[match_product_id]['clicks'] = 0 # 클릭
                facebook_info[match_product_id]['impressions'] = 0 # 노출
                facebook_info[match_product_id]['spend'] = 0 # 일예산
            try:
                facebook_info[match_product_id]['clicks'] += int((ins._data[AdsInsights.Field.outbound_clicks])[0]['1d_click'])
            except:
                pass
            facebook_info[match_product_id]['impressions'] += int(ins._data[AdsInsights.Field.impressions])
            facebook_info[match_product_id]['spend'] += int(ins._data[AdsInsights.Field.spend])

            product_ids.append(match_product_id)

    res = {}
    sku_code_dict = get_sku_code()
    sku_extra_name_dict = get_sku_extra_name()
    sku_name_dict = get_sku_name()

    products = Product.objects.filter(brand__name="...", is_outside=2, id__in=product_ids).prefetch_related('skus', 'detail') # 특정 브랜드의 광고 관련 stat 추출하기

    for product in products:
        for sku in product.skus.filter(status='A'):
            commission = 0
            try:
                commission = product.detail.commission # 수수료가 제대로 입력이 안되어 있는 경우가 있다!
            except:
                pass
            if commission == 0:
                commission = sku.commission

            if sku_extra_name_dict.get(sku.id) is None:
                res[sku.id] = get_default_dict(sku_code_dict[sku.id], sku_name_dict[sku.id],
                                               False, product.name, product.id, commission)
            else:
                res[sku.id] = get_default_dict(sku_code_dict[sku.id], sku_extra_name_dict[sku.id],
                                               True, product.name, product.id, commission)

            res[sku.id]['clicks'] = facebook_info[product.id]['clicks']
            res[sku.id]['impressions'] = facebook_info[product.id]['impressions']
            res[sku.id]['spend'] = facebook_info[product.id]['spend']

    ck_product_list = Product.objects.filter(brand__name="...", is_outside=2).values_list('id', flat=True)

    # 결제기준
    order_cart_item_list = CartItemStatusLog.objects.filter(create_date_time__gte=target_date,
                                                            create_date_time__lt=now_date,
                                                            status=2).values_list('cart_item', flat=True)

    order_cart_items = CartItem.objects.filter(id__in=order_cart_item_list, product_id__in=ck_product_list)\
        .prefetch_related('product', 'product__detail', 'sku')

    for cart_item in order_cart_items:
        if res.get(cart_item.sku_id) is None:
            commission = 0
            try:
                commission = cart_item.product.detail.commission
            except:
                pass
            if commission == 0:
                commission = cart_item.sku.commission

            if sku_extra_name_dict.get(cart_item.sku_id) is None:
                res[cart_item.sku_id] = get_default_dict(sku_code_dict[cart_item.sku_id], sku_name_dict[cart_item.sku_id],
                                                         False, product.name, product.id, commission)
            else:
                res[cart_item.sku_id] = get_default_dict(sku_code_dict[cart_item.sku_id], sku_extra_name_dict[cart_item.sku_id],
                                                         True, cart_item.product.name, cart_item.product_id, commission)

        res[cart_item.sku_id]['total_count'] += cart_item.count
        res[cart_item.sku_id]['total_price'] += cart_item.price * cart_item.count

    # 환불일 기준
    payment_cancels = PaymentCancel.objects.filter(created_date_time__gte=target_date, created_date_time__lt=now_date)

    cancel_group_ids = payment_cancels.values_list('delivery_group', flat=True).distinct()
    cancel_cart_items = CartItem.objects.filter(
        order__in=cancel_group_ids, status__in=[8, 10], product__id__in=ck_product_list) \
        .prefetch_related('product', 'product__detail', 'sku')

    for cart_item in cancel_cart_items:
        if res.get(cart_item.sku_id) is None:
            commission = 0
            try:
                commission = cart_item.product.detail.commission
            except:
                pass
            if commission == 0:
                commission = cart_item.sku.commission

            if sku_extra_name_dict.get(cart_item.sku_id) is None:
                res[cart_item.sku_id] = get_default_dict(sku_code_dict[cart_item.sku_id], sku_name_dict[cart_item.sku_id],
                                                         False, product.name, product.id, commission)
            else:
                res[cart_item.sku_id] = get_default_dict(sku_code_dict[cart_item.sku_id], sku_extra_name_dict[cart_item.sku_id],
                                                         True, cart_item.product.name, cart_item.product_id, commission)

        res[cart_item.sku_id]['total_count'] -= cart_item.count
        res[cart_item.sku_id]['total_price'] -= cart_item.price * cart_item.count

    product_id_list = list(ck_product_list)
    pageviews = AnalyticsCachePageviewMenuDetail.objects.filter(theday__gte=target_date, theday__lt=now_date,
                                                                type='furniture', type_idx__in=product_id_list).order_by('type_idx')

    pv_dict = {}
    ck_pv_product_list = []
    for pageview in pageviews:
        if pv_dict.get(pageview.type_idx) is None:
            pv_dict[pageview.type_idx] = 0
            ck_pv_product_list.append(pageview.type_idx)
        pv_dict[pageview.type_idx] += pageview.total_count

    products = Product.objects.filter(id__in=ck_pv_product_list).prefetch_related('skus', 'detail')
    for product in products:
        for sku in product.skus.filter(status='A'):
            commission = 0
            try:
                commission = product.detail.commission
            except:
                pass
            if commission == 0:
                commission = sku.commission

            if res.get(sku.id) is None:
                if sku_extra_name_dict.get(sku.id) is None:
                    res[sku.id] = get_default_dict(sku_code_dict[sku.id], sku_name_dict[sku.id],
                                                   False, product.name, product.id, commission)
                else:
                    res[sku.id] = get_default_dict(sku_code_dict[sku.id], sku_extra_name_dict[sku.id],
                                                   True, product.name, product.id, commission)
            res[sku.id]['daily_view'] = pv_dict[product.id]

    arche_perpo_write(res, target_date, now_date)
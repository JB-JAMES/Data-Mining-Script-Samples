from ggumim_api_server.response import response
from rest_framework import status
from django.db.models import Prefetch
from rest_framework.decorators import api_view

from core.models import LogMemberGrade, LogCartItem, ProductMainImage, Member
from mobile.constants import DumpTypes, DumpLevels
from datetime import datetime, timedelta


@api_view(['GET'])
def get_styling_member_list(req):
    res = {}

    log_members = LogMemberGrade.objects.all().prefetch_related('member').order_by('member_id', 'created_date_time')

    member_list = []
    member_set = {'order_time':[]}
    ck = {}
    before_day = None
    for log in log_members:
        if ck.get(log.member) is None:
            if before_day is not None:
                date_range = [before_day.date(), (before_day+timedelta(days=28)).date()]
                member_set['order_time'].append(date_range)
            if len(member_set['order_time'])>0:
                member_list.append(member_set)
            member_set = log.member.dumps(DumpTypes.SIMPLE, DumpLevels.CLIENT)
            member_set['name'] = "{0}({1})".format(member_set['name'], member_set['nickname'])
            member_set['order_time'] = []
            ck[log.member]=True
            before_day = None

        if log.special_grade_idx == 6:
            before_day = log.created_date_time

        if log.special_grade_idx is not None and before_day is not None and before_day != log.created_date_time:
            if before_day+timedelta(days=8) < log.created_date_time:
                date_range = [before_day.date(), log.created_date_time.date()]
                member_set['order_time'].append(date_range)
            before_day = None

    if before_day is not None:
        date_range = [before_day.date(), (before_day+timedelta(days=28)).date()]
        member_set['order_time'].append(date_range)
        member_list.append(member_set)

    res['list'] = sorted(member_list, key=lambda x: x['order_time'][-1][0], reverse=True)

    return response(res, status_number=status.HTTP_200_OK)


@api_view(['GET'])
def get_styling_product_list(req):

    member_id = req.GET.get('member_id', '')
    if member_id == '':
        return response({'msg': "menu id error"}, status_number=status.HTTP_500_INTERNAL_SERVER_ERROR)
    res = {}
    res['member_info'] = Member.objects.get(id=member_id).dumps(DumpTypes.SIMPLE, DumpLevels.CLIENT)
    log_members = LogMemberGrade.objects.filter(member_id=member_id).order_by('created_date_time')

    order_date = []
    before_day = None
    for log in log_members:
        if log.special_grade_idx == 6:
            before_day = log.created_date_time

        if log.special_grade_idx is not None and before_day is not None and before_day != log.created_date_time:
            if before_day+timedelta(days=8) < log.created_date_time:
                date_range = [before_day, log.created_date_time]
                order_date.append(date_range)
            before_day = None

    if before_day is not None:
        date_range = [before_day, before_day+timedelta(days=28)]
        order_date.append(date_range)

    STATUS_STR = {-3: '취소', -2: '즉시구매', -1: '취소', 0: '장바구니', 1: '결제 대기', 2: '상품 준비중', 3: '배송 대기', 4: '배송 지연', 5: '배송 중', 6: '배송 완료', 7: '입금전 취소', 8: '환불', 9: '교환', 10: '반품'}

    list = []
    for date in order_date:
        styling_set = {}

        styling_set['start_date'] = date[0]
        styling_set['end_date'] = date[1]

        log_cart_items = LogCartItem.objects.prefetch_related('cart_item', 'cart_item__order', 'cart_item__product', 'cart_item__product__brand',
        Prefetch(
            'cart_item__product__product_main_images',
            queryset=ProductMainImage.objects.filter(status='A').order_by('sort_idx'),
            to_attr='images'
        )).filter(member_id=member_id).order_by('cart_item_id', 'id')

        cart_item_list = {}
        order_cart_item_list = {}
        ck_cart_item_list = {}
        for log_cart_item in log_cart_items:
            if log_cart_item.cart_item.order is not None:
                if log_cart_item.cart_item.order.create_date_time >= date[0] and log_cart_item.cart_item.order.create_date_time <= date[1]:
                    if order_cart_item_list.get(log_cart_item.cart_item.order) is None:
                        order_cart_item_list[log_cart_item.cart_item.order] = []
                    if ck_cart_item_list.get(log_cart_item.cart_item) is None:
                        order_cart_item_list[log_cart_item.cart_item.order].append(log_cart_item.cart_item)
                        ck_cart_item_list[log_cart_item.cart_item] = True

            if cart_item_list.get(log_cart_item.cart_item) is None:
                cart_item_list[log_cart_item.cart_item] = True

            if log_cart_item.trigger_status == 'I':
                cart_item_list[log_cart_item.cart_item] = False

        ck_styling_sku = {}
        styling_set['stylist_pick'] = []
        styling_set['total_styling_price'] = 0
        for cart_item in cart_item_list:
            if cart_item_list[cart_item] is True:
                ck_styling_sku[cart_item.sku_id] = True
                unit_set = {}

                unit_set['product_info'] = cart_item.product.dumps(DumpTypes.SIMPLE, DumpLevels.CLIENT)
                unit_set['option_name'] = cart_item.unit_name
                unit_set['price'] = cart_item.price
                unit_set['count'] = cart_item.count
                unit_set['total_price'] = cart_item.price * cart_item.count
                unit_set['status'] = STATUS_STR[cart_item.status]

                styling_set['total_styling_price'] += cart_item.price * cart_item.count #

                styling_set['stylist_pick'].append(unit_set)

        styling_set['member_order_list'] = []
        order_styling_price = 0 #
        total_order_price = 0 #
        for order in order_cart_item_list:
            order_set = {}

            order_set['order_id'] = order.id
            order_set['deposit_date'] = order.deposit_date
            order_set['total_order_price'] = order.total_order_price
            order_set['total_delivery_price'] = order.total_delivery_price
            order_set['discount_rate'] = order.discount_rate

            order_set['cart_list'] = []
            for cart_item in order_cart_item_list[order]:
                unit_set = {}

                unit_set['product_info'] = cart_item.product.dumps(DumpTypes.SIMPLE, DumpLevels.CLIENT)
                unit_set['option_name'] = cart_item.unit_name
                unit_set['price'] = cart_item.price
                unit_set['count'] = cart_item.count
                unit_set['total_price'] = cart_item.price * cart_item.count
                unit_set['status'] = STATUS_STR[cart_item.status]

                if cart_item.status in [-2,2,3,4,5,6,7,8,10]:
                    total_order_price += cart_item.price * cart_item.count #

                if ck_styling_sku.get(cart_item.sku_id) is None:
                    unit_set['is_styling'] = False
                else:
                    unit_set['is_styling'] = True
                    if cart_item.status in [-2,2,3,4,5,6,7,8,10]:
                        order_styling_price += cart_item.price * cart_item.count #

                order_set['cart_list'].append(unit_set)

            styling_set['member_order_list'].append(order_set)

            styling_set['discount_styling_price'] = int(styling_set['total_styling_price'] * 0.95)
            styling_set['discount_order_styling_price'] = int(order_styling_price * 0.95)
            styling_set['order_styling_rate'] = None if styling_set['total_styling_price'] == 0 \
                else round(order_styling_price*100 / styling_set['total_styling_price'],2)
            styling_set['discount_order_price'] = int(total_order_price * 0.95)
            styling_set['total_order_rate'] = None if styling_set['total_styling_price'] == 0 \
                else round(total_order_price*100 / styling_set['total_styling_price'],2)

        list.append(styling_set)

    res['list'] = list

    return response(res, status.HTTP_200_OK)
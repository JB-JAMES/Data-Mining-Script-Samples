from core.models import CartItem, Order, Product, PaymentCancel, ProductDetail, AnalyticsCachePageviewMenuDetail, CartItemStatusLog
from analysis.spreadsheet import write_sheet


def get_partner(products):
    fps = ProductDetail.objects.filter(product__in=products).prefetch_related('partner')
    dict = {0: None, None: None}
    for fp in fps:
        dict[fp.product_id] = fp.partner.name

    return dict


def get_periodic_stat(before_day, day, per):

    status = [-2, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10]

    # 장바구니 기준
    cart_items = CartItem.objects.filter(create_date_time__gte=before_day,
                                         create_date_time__lt=day, status__in=status).prefetch_related('product', 'product__brand')

    product_ids1 = cart_items.values_list('product', flat=True).distinct()

    # 결졔일 기준
    order_cart_item_list = CartItemStatusLog.objects.filter(create_date_time__gte=before_day, create_date_time__lt=day,
                                                            status=2).values_list('cart_item', flat=True)

    order_cart_items = CartItem.objects.filter(id__in=order_cart_item_list).prefetch_related(
        'product', 'product__brand', 'product__detail', 'order')

    product_ids2 = order_cart_items.values_list('product', flat=True).distinct()

    # 환불일 기준
    payment_cancels = PaymentCancel.objects.filter(created_date_time__gte=before_day, created_date_time__lt=day)

    total_refund_price = 0
    for payment_cancel in payment_cancels:
        total_refund_price += payment_cancel.cancel_amt

    cancel_group_ids = payment_cancels.values_list('delivery_group', flat=True).distinct()
    cancel_cart_items = CartItem.objects.filter(
        order__in=cancel_group_ids, status__in=[8, 10]).prefetch_related('product', 'product__brand', 'product__detail', 'order')

    product_ids3 = cancel_cart_items.values_list('product', flat=True).distinct()

    # 최종 제품 목록
    products = Product.objects.filter(id__in=product_ids1 | product_ids2 | product_ids3).prefetch_related('brand', 'detail').order_by('id')

    # 제품의 공급사 찾기
    partner_dict = get_partner(products)

    result_total = {}

    result_total['price'] = 0 # 누적 매출액
    result_total['normal_price'] = 0 # 누적 일반 매출액
    result_total['detail_price'] = 0 # 누적 상세 매출액

    result_total['sale_price'] = 0 # 누적 판매액
    result_total['delivery_price'] = 0 # 누적 배달액
    result_total['refund_price'] = 0 # 누적 환불액

    result_total['pageview'] = 0 # 누적 PV
    result_total['normal_pageview'] = 0 # 누적 일반 PV
    result_total['detail_pageview'] = 0 # 누적 상세 PV
    result_total['cart_product'] = 0 # 누적 장바구니 상품 수

    result_total['sale_product'] = 0 # 누적 판매 상품 수
    result_total['normal_product'] = 0 # 누적 판매 일반 상품 수
    result_total['detail_product'] = 0 # 누적 판매 상세 상품 수

    result_total['sale_product_count'] = 0 # 누적 판매 일반 상품 수(SKU 개수)
    result_total['normal_product_count'] = 0 # 누적 판매 일반 상품 수(SKU 개수)
    result_total['detail_product_count'] = 0 # 누적 판매 상세 상품 수(SKU 개수)
    result_total['cart_product_count'] = 0 # 누적 장바구니 상품 수(SKU 개수)

    result = {}
    for product in products:
        result[product.id] = {}
        result[product.id]['info'] = {'name': product.name, 'brand': None if product.brand_id == 0 else product.brand.name,
                                      'partner': partner_dict.get(product.id), 'created_date': product.created_date_time,
                                      'is_partner': True if product.detail.is_partner == 1 else False, 'price': product.price_discount}
        result[product.id]['cart_count'] = 0

        result[product.id]['sale_main_count'] = 0
        result[product.id]['sale_extra_count'] = 0
        result[product.id]['sale_main_price'] = 0
        result[product.id]['sale_extra_price'] = 0
        result[product.id]['sale_total_price'] = 0

        result[product.id]['refund_main_count'] = 0
        result[product.id]['refund_extra_count'] = 0
        result[product.id]['refund_main_price'] = 0
        result[product.id]['refund_extra_price'] = 0
        result[product.id]['refund_total_price'] = 0

        result[product.id]['daily_view'] = 0

        result[product.id]['total_price'] = 0

    # 장바구니 counting
    for cart_item in cart_items:
        if cart_item.parent_unit_idx != 0 or cart_item.count is None:
            continue
        if result[cart_item.product_id]['cart_count'] == 0:
            result_total['cart_product'] += 1

        result[cart_item.product_id]['cart_count'] += cart_item.count
        result_total['cart_product_count'] += cart_item.count

    # 구매 관련 counting
    for cart_item in order_cart_items:
        # 메인 상품일때
        if cart_item.parent_unit_idx == 0:
            # 상품 종류 개수 counting
            if result[cart_item.product_id]['sale_main_count'] == 0:
                result_total['sale_product'] += 1
                if cart_item.product.detail.is_partner == 1: # 일반 상품일때,
                    result_total['normal_product'] += 1
                else: # 상세 상품일때,
                    result_total['detail_product'] += 1

            result[cart_item.product_id]['sale_main_count'] += cart_item.count
            result[cart_item.product_id]['sale_main_price'] += cart_item.price * cart_item.count

            # 상품수 counting
            result_total['sale_product_count'] += 1
            if cart_item.product.detail.is_partner == 1: # 일반 상품일때,
                result_total['normal_product_count'] += 1
            else: # 상세 상품일때,
                result_total['detail_product_count'] += 1

        else:
            result[cart_item.product_id]['sale_extra_count'] += cart_item.count
            result[cart_item.product_id]['sale_extra_price'] += cart_item.price * cart_item.count

        # 판매 금액
        result[cart_item.product_id]['sale_total_price'] += cart_item.price * cart_item.count
        result[cart_item.product_id]['total_price'] += cart_item.price * cart_item.count

        result_total['sale_price'] += cart_item.count * cart_item.price
        if cart_item.product.detail.is_partner == 1: # 일반 상품일때,
            result_total['normal_price'] += cart_item.count * cart_item.price
        else: # 상세 상품일때,
            result_total['detail_price'] += cart_item.count * cart_item.price

    # 환불 관련 counting
    for cart_item in cancel_cart_items:
        if cart_item.parent_unit_idx == 0:
            result[cart_item.product_id]['refund_main_count'] += cart_item.count
            result[cart_item.product_id]['refund_main_price'] += cart_item.price * cart_item.count

        else:
            result[cart_item.product_id]['refund_extra_count'] += cart_item.count
            result[cart_item.product_id]['refund_extra_price'] += cart_item.price * cart_item.count

        result[cart_item.product_id]['refund_total_price'] += cart_item.price * cart_item.count
        result[cart_item.product_id]['total_price'] -= cart_item.price * cart_item.count

        result_total['refund_price'] += cart_item.price * cart_item.count
        if cart_item.product.detail.is_partner == 1: # 일반 상품일때,
            result_total['normal_price'] -= cart_item.count * cart_item.price
        else: # 상세 상품일때,
            result_total['detail_price'] -= cart_item.count * cart_item.price

    # 배달비 총 합산
    check = {}
    for cart_item in order_cart_items:
        if check.get(cart_item.order) is None:
            result_total['delivery_price'] += cart_item.order.total_delivery_price
            check[cart_item.order] = 1

    # 노출수 counting
    pageviews = AnalyticsCachePageviewMenuDetail.objects.filter(theday__gte=before_day, theday__lt=day,
                                                                type='furniture', type_idx__in=products).order_by('type_idx')
    for pageview in pageviews:
        result[pageview.type_idx]['daily_view'] += pageview.total_count
        result_total['pageview'] += pageview.total_count

    result_total['price'] = result_total['normal_price'] + result_total['detail_price']

    write_sheet.stat_write(result, result_total, products.count(), before_day, day, per)
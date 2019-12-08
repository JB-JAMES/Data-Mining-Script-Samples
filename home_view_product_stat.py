from mobile.models import HomeContent, HomeComponent
from core.models import Product, CartItem, AnalyticsCachePageviewMenuDetail, CartItemStatusLog, PaymentCancel
from datetime import timedelta

from analysis.spreadsheet.write_sheet import home_view_product_write


def stat(date):

    contents = HomeContent.objects.filter(created_date_time__gte=date-timedelta(days=1), created_date_time__lt=date,
                                          product_id__gte=1).prefetch_related('component', 'component__slot')

    product_dict = {}
    for content in contents:
        title = content.component.title if content.component.title == content.component.slot.title \
                else content.component.slot.title + "-" + content.component.title
        if product_dict.get(content.product_id) is None:
            product_dict[content.product_id] = ""
        if product_dict[content.product_id].find(title) == -1:
            product_dict[content.product_id] = product_dict[content.product_id] + " / " + title

    components = HomeComponent.objects.filter(slot__is_available=True, slot__is_visible=True,
                                              slot__menu__is_available=True, slot__menu__is_visible=True,
                                              is_auto_generated=False).order_by('slot_id', '-created_date_time')
    component_ids = []
    slot_ck = {}
    for component in components:
        if component.created_date_time >= date:
            pass
        elif component.created_date_time < date and component.created_date_time >= date-timedelta(days=1):
            component_ids.append(component.id)
        elif slot_ck.get(component.slot_id) is None:
            component_ids.append(component.id)
            slot_ck[component.slot_id] = True

    contents = HomeContent.objects.filter(component_id__in=component_ids, product_id__gte=1).prefetch_related('component', 'component__slot')

    for content in contents:
        title = content.component.title if content.component.title == content.component.slot.title \
            else content.component.slot.title + "-" + content.component.title
        if product_dict.get(content.product_id) is None:
            product_dict[content.product_id] = ""
        if product_dict[content.product_id].find(title) == -1:
            product_dict[content.product_id] = product_dict[content.product_id] + " / " + title

    product_ids = list(product_dict.keys())

    results = {}
    products = Product.objects.filter(id__in=product_ids)
    for product in products:
        results[product.id] = {}
        results[product.id]['name'] = product.name
        results[product.id]['section'] = product_dict[product.id]
        results[product.id]['total_count'] = 0
        results[product.id]['total_price'] = 0
        results[product.id]['daily_view'] = 0

    # 결제기준
    order_cart_item_list = CartItemStatusLog.objects.filter(create_date_time__gte=date-timedelta(days=1),
                                                            create_date_time__lt=date,
                                                            status=2, cart_item__product__id__in=product_ids) \
        .values_list('cart_item', flat=True)

    order_cart_items = CartItem.objects.filter(id__in=order_cart_item_list).prefetch_related('product', 'order')

    for cart_item in order_cart_items:
        # 메인 상품일때
        if cart_item.parent_unit_idx == 0:
            # 상품 종류 개수 counting
            results[cart_item.product_id]['total_price'] += cart_item.count * cart_item.price
            results[cart_item.product_id]['total_count'] += cart_item.count

    # 환불일 기준
    payment_cancels = PaymentCancel.objects.filter(created_date_time__gte=date-timedelta(days=1), created_date_time__lt=date)

    cancel_group_ids = payment_cancels.values_list('delivery_group', flat=True).distinct()
    cancel_cart_items = CartItem.objects.filter(
        order__in=cancel_group_ids, status__in=[8, 10], product__id__in=product_ids) \
        .prefetch_related('product', 'order')

    for cart_item in cancel_cart_items:
        if cart_item.parent_unit_idx == 0:
            results[cart_item.product_id]['total_price'] -= cart_item.count * cart_item.price
            results[cart_item.product_id]['total_count'] -= cart_item.count

    pageviews = AnalyticsCachePageviewMenuDetail.objects.filter(theday__gte=date-timedelta(days=1), theday__lt=date,
                                                                type='furniture', type_idx__in=product_ids).order_by('type_idx')
    for pageview in pageviews:
        results[pageview.type_idx]['daily_view'] += pageview.total_count

    home_view_product_write(results, date)
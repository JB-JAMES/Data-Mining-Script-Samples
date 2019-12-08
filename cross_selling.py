from core.models import CartItem, Order, Product, PaymentCancel, ProductDetail, AnalyticsCachePageviewMenuDetail
from datetime import timedelta
from analysis.spreadsheet import write_sheet
from analysis.constants import *
from scripts.data_collecting import get_year_month


def get_monthes():
    return ['2018-7', '2018-8', '2018-9', '2018-10']


def get_most_paid_products(price=300000): # 30만원 이상 주문 관련

    orders = Order.objects.filter(deposit_date__gte='2018-07-01', total_order_price__gte=price).prefetch_related('cart_items')
    order_ids = []
    for order in orders:
        if order.cart_items.count() > 1:
            order_ids.append(order.id)

    cart_items = CartItem.objects.filter(order_id__in=order_ids).prefetch_related('product', 'order')

    products = {}
    months = []

    for cart_item in cart_items:
        month = get_year_month(cart_item.order.deposit_date)
        if month not in products:
            print(month)
            months.append(month)
            products[month] = {}

        if cart_item.product.id in products[month]:
            products[month][cart_item.product.id]['count'] += cart_item.count
            products[month][cart_item.product.id]['price_sum'] += cart_item.price * cart_item.count
            products[month][cart_item.product.id]['order_sum'] += cart_item.order.total_order_price
            products[month][cart_item.product.id]['order_count'] += 1
        else:
            products[month][cart_item.product.id] = {}
            products[month][cart_item.product.id]['count'] = cart_item.count
            products[month][cart_item.product.id]['price_sum'] = cart_item.price * cart_item.count
            products[month][cart_item.product.id]['product'] = cart_item.product
            products[month][cart_item.product.id]['order_sum'] = cart_item.order.total_order_price
            products[month][cart_item.product.id]['order_count'] = 1


    for month in months:
        with open('cross_selling_{0}.txt'.format(month), "w") as f:
            sorted_ids = sorted(products[month], key=lambda x: products[month][x]["order_count"], reverse=True)
            print("상품번호", "상품명", "주문수", "총 주문 판매량 합", "총 상품 판매량 합", sep="\t", file=f, end='\n')
            for id in sorted_ids:
                print(products[month][id]['product'].id, products[month][id]['product'].name, products[month][id]['order_count'], \
                      products[month][id]['order_sum'], products[month][id]['price_sum'], sep="\t", file=f, end='\n')
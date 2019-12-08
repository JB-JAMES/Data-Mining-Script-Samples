# 분기 내 여러 Stat 추출
from core.models import Member, CartItem, Order, Product
from datetime import datetime


## cross_selling 2018 10 이후 교차 구매 수량
def change_number(number):
    if number > 5:
        return 5
    return number


# 교차구매
def cross_selling(start_date, end_date):
    cart_items = CartItem.objects.prefetch_related('order').filter(order__deposit_date__gt=start_date,
                                                                   order__deposit_date__lt=end_date).prefetch_related(
        'product') # 주문날 기준으로 장바구니 목록을 끌어온다

    dict_order_product = {} # 상품 목록 만들기
    for cart_item in cart_items:
        if dict_order_product.get(cart_item.order_id) is None:
            dict_order_product[cart_item.order_id] = []
        if cart_item.parent_unit_idx > 0:  # 추가 상품 제거
            continue
        dict = {
            'product_id': cart_item.product_id,
            'name': cart_item.product.name,
            'price': cart_item.count * cart_item.price
        }
        dict_order_product[cart_item.order_id].append(dict)  # 주문별로 상품목록 추가

    # 교차된 횟수
    product_rank = {
        2: {},
        3: {},
        4: {},
        5: {}
    }

    for id in dict_order_product:
        if len(dict_order_product[id]) < 2:  # 단독 주문 제외
            continue
        for cart_item in dict_order_product[id]:
            if product_rank[change_number(len(dict_order_product[id]))].get(
                    cart_item['product_id']) is None:  # n개 구매 일때 product_rank[n]
                product_rank[change_number(len(dict_order_product[id]))][cart_item['product_id']] = {
                    'name': cart_item['name'],
                    'price': 0
                }
            product_rank[change_number(len(dict_order_product[id]))][cart_item['product_id']]['price'] += cart_item[
                'price']

    for i in range(2, 6):
        with open("res{0}.txt".format(i), "w") as f:
            sort_ids = sorted(product_rank[i], key=lambda x: product_rank[i][x]['price'], reverse=True)
            rank = 1
            for id in sort_ids:
                if rank > 100:
                    break
                print(rank, id, product_rank[i][id]['name'], product_rank[i][id]['price'], file=f, sep='\t', end='\n')
                rank += 1


## 두번째 order에 많이 팔린 상품
## 두번째 구매까지 평균 소요시간
def order_stat(start_date, end_date):
    members = Member.objects.all()

    member_orders = {}
    order_dict = {}

    for order in Order.objects.filter(deposit_date__gte=start_date, deposit_date__lt=end_date):
        order_dict[order.id] = order

    for cart in CartItem.objects.all():
        if cart.order_id is not None and cart.member_id > 0:
            if cart.member_id not in member_orders:
                member_orders[cart.member_id] = []

            if order_dict.get(cart.order_id) is None:
                continue

            if cart.order_id not in member_orders[cart.member_id] and order_dict[
                cart.order_id].deposit_date is not None:
                member_orders[cart.member_id].append(cart.order_id)


    order_ids = [[], [], [], []] # 각각 2,3,4,5 교차된

    for id in member_orders:
        for idx in range(len(member_orders[id]) - 1):
            if idx == 0:
                continue
            order_ids[change_number(idx - 1)].append(member_orders[id][change_number(idx - 1)])

    cart_items = CartItem.objects.prefetch_related('order').filter(order__deposit_date__gt=start_date,
                                                                   order__deposit_date__lt=end_date).prefetch_related(
        'product')

    dict_order_product = {}
    for cart_item in cart_items:
        if dict_order_product.get(cart_item.order_id) is None:
            dict_order_product[cart_item.order_id] = []
        if cart_item.parent_unit_idx > 0:  # 추가 상품 제거
            continue
        dict = {
            'product_id': cart_item.product_id,
            'name': cart_item.product.name,
            'price': cart_item.count * cart_item.price
        }
        dict_order_product[cart_item.order_id].append(dict)

    for idx in range(0, 4):
        with open("{}th_selling.txt".format(idx + 2), "w") as f:
            dict = {}
            for order_id in order_ids[idx]:

                for cart in dict_order_product[order_id]:
                    if dict.get(cart['product_id']) is None:
                        dict[cart['product_id']] = {
                            'name': cart['name'],
                            'price': 0
                        }
                    dict[cart['product_id']]['price'] += cart['price']

            sort_ids = sorted(dict, key=lambda x: dict[x]['price'], reverse=True)

            rank = 1
            for id in sort_ids:
                print(rank, id, dict[id]['name'], dict[id]['price'], file=f, sep='\t', end='\n')
                rank += 1


## 2018 10 이전 이후 가입자의 재구매율 (1회구매 2회구매 3회구매 4회구매 5회구매 이상)
def repeat_selling(start_date, end_date):
    member_before = Member.objects.filter(created_date_time__lt=start_date)
    member_after = Member.objects.filter(created_date_time__gte=start_date, created_date_time__lt=end_date)

    member_orders = {}
    order_dict = {}

    for order in Order.objects.all():
        order_dict[order.id] = order

    for cart in CartItem.objects.all():
        if cart.order_id is not None and cart.member_id > 0:
            if cart.member_id not in member_orders:
                member_orders[cart.member_id] = []

            if order_dict.get(cart.order_id) is None:
                continue

            if cart.order_id not in member_orders[cart.member_id] and order_dict[
                cart.order_id].deposit_date is not None:
                member_orders[cart.member_id].append(cart.order_id)

    counts = [0, 0, 0, 0, 0]
    terms = [0, 0, 0, 0, 0]
    for member in member_before:
        if member_orders.get(member.id) is None:
            continue

        count = len(member_orders[member.id])
        if count > 5:
            count = 5
        if count == 0:
            continue
        counts[count - 1] += 1
        for idx in range(len(member_orders[member.id]) - 1):
            before_id = member_orders[member.id][idx]
            after_id = member_orders[member.id][idx + 1]

            before_order = order_dict[before_id]
            after_order = order_dict[after_id]

            delta = after_order.deposit_date - before_order.deposit_date

            terms[idx] += delta.seconds

    with open("stat.txt", "w") as f:
        print("before stat", end="\n", file=f)
        print("total: ", len(member_before), end="\n", file=f, sep='\t')
        print(counts[0], counts[1], counts[2], counts[3], counts[4], end="\n", file=f, sep='\t')
        print(terms[0], terms[1], terms[2], terms[3], end="\n", file=f, sep='\t')

    counts = [0, 0, 0, 0, 0]
    terms = [0, 0, 0, 0, 0]
    for member in member_after:
        if member_orders.get(member.id) is None:
            continue
        count = len(member_orders[member.id])
        if count > 5:
            count = 5
        if count == 0:
            continue
        counts[count - 1] += 1
        for idx in range(len(member_orders[member.id]) - 1):
            before_id = member_orders[member.id][idx]
            after_id = member_orders[member.id][idx + 1]

            before_order = order_dict[before_id]
            after_order = order_dict[after_id]

            delta = after_order.deposit_date - before_order.deposit_date

            terms[idx] += delta.seconds


    with open("stat_after.txt", "w") as f:
        print("after stat", end="\n", file=f)
        print("total: ", len(member_after), end="\n", file=f, sep='\t')
        print(counts[0], counts[1], counts[2], counts[3], counts[4], end="\n", file=f, sep='\t')
        print(terms[0], terms[1], terms[2], terms[3], end="\n", file=f, sep='\t')


def run():
    start_date = datetime.strptime("2018-10-01", "%Y-%m-%d")
    end_date = datetime.strptime("2019-01-31", "%Y-%m-%d")
    order_stat(start_date, end_date)

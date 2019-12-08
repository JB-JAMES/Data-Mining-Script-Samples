from core.models import Order, CartItem, Product, CartItemStatusLog, ProductCategory, AnalyticsCachePageviewMenuDetail

from datetime import datetime, timedelta


# 단 한번이라도 팔린 기록이 있는 상품 목록 추출
def get_product_sold_even_once():
    paid_products = Order.objects.exclude(deposit_date=None) \
        .prefetch_related('cart_items', 'cart_items__sku', 'cart_items__sku__product',
                          'cart_items__sku__product__product_categories__category') \
        .values_list('cart_items__sku__product', flat=True).distinct()

    print("size:", len(paid_products))
    return paid_products


def get_product_sold_even_once_v2():
    paid_products = CartItemStatusLog.objects.filter(status=2).values_list('cart_item__product', flat=True).distinct()

    print("size:", len(paid_products))
    return paid_products


def get_year_month(date):
    return str(date.year) + '-' + str(date.month)


def get_my_categories(product, product_categories):
    categories = []
    for pc in product_categories.filter(product=product):
        categories.append(pc.category.name)

    return list(set(categories))


def get_category_dict(products_ids):
    product_categories = ProductCategory.objects.prefetch_related('category').filter(product__id__in=products_ids)

    dict = {}
    for pc in product_categories:
        pid = pc.product_id
        print(pc.id)
        if pc.category is None:
            continue
        if pc.category.status is 'D':
            continue
        if pid in dict:
            dict[pid].append(pc.category.name)
        else:
            dict[pid] = [pc.category.name]

    return dict


def get_categories(products_ids):
    products = Product.objects.filter(id__in=products_ids).prefetch_related('brand', 'detail__partner',
                                                                            'reviews').order_by('id')
    category_dict = get_category_dict(products_ids)
    one_depth_categories = ["가구", "가전", "생활 • 수납", "패브릭", "주방", "홈데코", "반려동식물"]
    no_one_depth = 0

    with open('상품정보.txt', 'w') as f:
        print("상품번호\t상품명\t브랜드\t공급사\t상세여부\t평점\t1depth카테고리\t나머지 카테고리", file=f, end='\n')
        for product in products:
            print(product.id, file=f, end='\t')
            print(product.name, file=f, end='\t')
            print(product.brand.name if product.brand is not None else "", file=f, end='\t')
            print(product.detail.partner.name if product.detail.partner is not None else "", file=f, end='\t')
            normal = "상세" if product.detail.is_partner is 0 else "일반"
            print(normal, file=f, end='\t')

            count = 0
            sum = 0
            for item in product.reviews.all():
                sum += item.score
                count += 1
            if count == 0:
                print("", file=f, end='\t')
            else:
                print("{0}".format(round(sum / count, 1)), file=f, end='\t')

            if product.id in category_dict:
                my_categories = category_dict[product.id]
            else:
                my_categories = []

            my_categories = list(set(my_categories))
            my_one_depth = ""
            for one_depth in one_depth_categories:
                if one_depth in my_categories:
                    my_one_depth = one_depth
                    break

            if my_one_depth == "":
                no_one_depth += 1
                print("없음", file=f, end='\t')
            else:
                my_categories.remove(my_one_depth)
                print(my_one_depth, file=f, end='\t')

            for category in my_categories:
                print(category, file=f, end='\t')

            print('', file=f, end='\n')

    print("no one depth category items:", no_one_depth)


def get_dates():
    start = datetime.strptime("2018-10-01", "%Y-%m-%d")
    end = datetime.strptime("2018-11-01", "%Y-%m-%d")

    return [(start + timedelta(days=x)).date() for x in range(0, (end - start).days)]


def get_monthes():
    return ['2018-10']


def get_pageview_dict():
    pgs = AnalyticsCachePageviewMenuDetail.objects.filter(type='furniture', status='A')
    dict = {0: None, None: None}
    for pg in pgs:
        if dict.get(pg.type_idx) is None:
            dict[pg.type_idx] = []
        dict[pg.type_idx].append(pg)
    return dict


def get_pv(products_ids):
    products = Product.objects.filter(id__in=products_ids).order_by('id')
    print('3')
    dates = get_dates()
    monthes = get_monthes()

    with open("pv(일).txt", 'w') as f:
        with open("pv(월).txt", 'w') as fm:
            print("\t", file=f, end='\t')
            for date in dates:
                print(date, file=f, end='\t')

            print("\t", file=fm, end='\t')
            for month in monthes:
                print("{0}".format(month), end="\t", file=fm)

            print('', file=fm, end='\n')
            print('', file=f, end='\n')
            pageviews = get_pageview_dict()
            print('4')
            for product in products:
                print(product.id, file=f, end='\t')
                print(product.name, file=f, end='\t')

                print(product.id, file=fm, end='\t')
                print(product.name, file=fm, end='\t')
                dates_pv = {}
                month_pv = {}

                if pageviews.get(product.id) is None:
                    print('', file=f, end='\n')
                    continue
                for pageview in pageviews[product.id]:
                    date = pageview.theday
                    month = get_year_month(pageview.theday)
                    if date in dates_pv:
                        dates_pv[date] = max(dates_pv[date], pageview.total_count)
                        month_pv[month] -= min(dates_pv[date], pageview.total_count)
                        month_pv[month] += max(dates_pv[date], pageview.total_count)
                    else:
                        dates_pv[date] = pageview.total_count

                        if month in month_pv:
                            month_pv[month] = month_pv[month] + pageview.total_count
                        else:
                            month_pv[month] = pageview.total_count

                for date in dates:
                    if date in dates_pv:
                        print(dates_pv[date], file=f, end="\t")
                    else:
                        print("", file=f, end="\t")

                print('', file=f, end='\n')

                for month in monthes:
                    if month in month_pv:
                        print(month_pv[month], file=fm, end="\t")
                    else:
                        print("", file=fm, end="\t")

                print('', file=fm, end='\n')


def get_cart_item(products_ids):
    products = Product.objects.filter(id__in=products_ids).prefetch_related('cart_items').order_by('id')
    print('1')
    dates = get_dates()
    monthes = get_monthes()

    with open("장바구니(일).txt", 'w') as f:
        with open("장바구니(월).txt", 'w') as fm:

            print("\t", file=f, end='\t')
            for date in dates:
                print(date, file=f, end='\t')
            print('', file=f, end='\n')

            print("\t", file=fm, end='\t')
            for month in monthes:
                print("{0}".format(month), end="\t", file=fm)
            print('', file=fm, end='\n')
            print('2')
            for product in products:
                print(product.id, file=f, end='\t')
                print(product.name, file=f, end='\t')

                print(product.id, file=fm, end='\t')
                print(product.name, file=fm, end='\t')

                month_cart = {}
                dates_cart = {}

                for item in product.cart_items.all():
                    date = item.create_date_time.date()
                    month = get_year_month(item.create_date_time)

                    if date in dates_cart:
                        dates_cart[date] += 1
                    else:
                        dates_cart[date] = 1

                    if month in month_cart:
                        month_cart[month] += 1
                    else:
                        month_cart[month] = 1

                for date in dates:
                    if date in dates_cart:
                        print(dates_cart[date], file=f, end="\t")
                    else:
                        print("", file=f, end="\t")

                print('', file=f, end='\n')

                for month in monthes:
                    if month in month_cart:
                        print(month_cart[month], file=fm, end="\t")
                    else:
                        print("", file=fm, end="\t")

                print('', file=fm, end='\n')


def get_paid_count(products_ids, is_refunded, is_counted):
    products = Product.objects.filter(id__in=products_ids).prefetch_related('cart_items').order_by('id')
    dates = get_dates()
    monthes = get_monthes()

    filename = '구매횟수'
    if is_refunded:
        filename = '반품횟수'
    if is_counted:
        filename = '구매수량'
        if is_refunded:
            filename = '반품수량'

    with open(filename + '(일).txt', 'w') as f:
        with open(filename + '(월).txt', 'w') as fm:
            print("\t", file=f, end='\t')
            for date in dates:
                print(date, file=f, end='\t')
            print('', file=f, end='\n')

            print("\t", file=fm, end='\t')
            for month in monthes:
                print("{0}".format(month), end="\t", file=fm)
            print('', file=fm, end='\n')

            for product in products:
                print(product.id, file=f, end='\t')
                print(product.name, file=f, end='\t')
                print(product.id, file=fm, end='\t')
                print(product.name, file=fm, end='\t')

                month_cart = {}
                dates_cart = {}

                status = [2, 3, 4, 5, 6, 8, 9, 10]
                if is_refunded:
                    status = [8, 10]

                for item in product.cart_items.filter(status__in=status).prefetch_related('order'):
                    if item.order is None:
                        continue
                    if item.order.deposit_date is None:
                        continue
                    date = item.order.deposit_date.date()
                    month = get_year_month(item.order.deposit_date.date())

                    if date in dates_cart:
                        if is_counted:
                            dates_cart[date] += item.count
                        else:
                            dates_cart[date] += 1
                    else:
                        if is_counted:
                            dates_cart[date] = item.count
                        else:
                            dates_cart[date] = 1

                    if month in month_cart:
                        if is_counted:
                            month_cart[month] += item.count
                        else:
                            month_cart[month] += 1
                    else:
                        if is_counted:
                            month_cart[month] = item.count
                        else:
                            month_cart[month] = 1

                for date in dates:
                    if date in dates_cart:
                        print(dates_cart[date], file=f, end="\t")
                    else:
                        print("", file=f, end="\t")

                print('', file=f, end='\n')

                for month in monthes:
                    if month in month_cart:
                        print(month_cart[month], file=fm, end="\t")
                    else:
                        print("", file=fm, end="\t")

                print('', file=fm, end='\n')


def get_review(products_ids):
    products = Product.objects.filter(id__in=products_ids).prefetch_related('reviews').order_by('id')
    dates = get_dates()
    monthes = get_monthes()

    with open("리뷰수(일).txt", 'w') as f:
        with open("리뷰수(월).txt", 'w') as fm:
            print("\t", file=f, end='\t')
            for date in dates:
                print(date, file=f, end='\t')
            print('', file=f, end='\n')

            print("\t", file=fm, end='\t')
            for month in monthes:
                print("{0}".format(month), end="\t", file=fm)
            print('', file=fm, end='\n')

            for product in products:
                print(product.id, file=f, end='\t')
                print(product.name, file=f, end='\t')
                print(product.id, file=fm, end='\t')
                print(product.name, file=fm, end='\t')

                month_cart = {}
                dates_cart = {}

                for item in product.reviews.all():
                    date = item.review_date_time.date()
                    if date in dates_cart:
                        dates_cart[date] += 1
                    else:
                        dates_cart[date] = 1

                    month = get_year_month(item.review_date_time)
                    if month in month_cart:
                        month_cart[month] += 1
                    else:
                        month_cart[month] = 1

                for date in dates:
                    if date in dates_cart:
                        print(dates_cart[date], file=f, end="\t")
                    else:
                        print("", file=f, end="\t")

                print('', file=f, end='\n')

                for month in monthes:
                    if month in month_cart:
                        print(month_cart[month], file=fm, end="\t")
                    else:
                        print("", file=fm, end="\t")

                print('', file=fm, end='\n')


def get_volume():
    orders = Order.objects.exclude(deposit_date=None).prefetch_related('cart_items', 'cart_items__product',
                                                                       'cart_items__sku')

    # 제품번호/주문번호/상품단가*개수/배송비 (묶음배송의 경우 구매 상품수로 1/n)/주문일/커미션
    month_dict = {}

    with open("주문정보.txt", 'w') as f:
        print("제품번호\t주문번호\t상품단가*개수\t배송비 (묶음배송의 경우 구매 상품수로 1/n)\t주문일\t커미션", file=f, end='\n')
        for order in orders:
            count = order.cart_items.count()

            for cart_item in order.cart_items.all():

                print(cart_item.product.id, file=f, end='\t')
                print(order.id, file=f, end='\t')
                print(cart_item.price * cart_item.count, file=f, end='\t')
                print(order.total_delivery_price / count, file=f, end='\t')
                print(order.create_date_time.date(), file=f, end='\t')
                print(cart_item.sku.commission, file=f, end='\n')
                month = get_year_month(order.create_date_time)
                if month in month_dict:
                    month_dict[month] += cart_item.price * cart_item.count
                else:
                    month_dict[month] = cart_item.price * cart_item.count

    for month in month_dict:
        print(month, ':', month_dict[month])


def get_volume_daily(products_ids):
    products = Product.objects.filter(id__in=products_ids).order_by('id')
    dates = get_dates()
    monthes = get_monthes()

    orders = Order.objects.exclude(deposit_date=None).prefetch_related('cart_items', 'cart_items__product',
                                                                       'cart_items__sku')

    product_dict = {}

    for order in orders:
        count = order.cart_items.count()

        for cart_item in order.cart_items.all():
            if cart_item.product.id in product_dict:
                product_dict[cart_item.product.id].append(
                    (cart_item.price * cart_item.count, order.total_delivery_price / count, order.create_date_time))
            else:
                product_dict[cart_item.product.id] = [
                    (cart_item.price * cart_item.count, order.total_delivery_price / count, order.create_date_time)]

    with open("거래량(일).txt", 'w') as f:
        with open("거래량(월).txt", 'w') as fm:
            print("\t", file=f, end='\t')
            for date in dates:
                print(date, file=f, end='\t')
            print('', file=f, end='\n')

            print("\t", file=fm, end='\t')
            for month in monthes:
                print("{0}".format(month), end="\t", file=fm)
            print('', file=fm, end='\n')

            for product in products:
                print(product.id, file=f, end='\t')
                print(product.name, file=f, end='\t')
                print(product.id, file=fm, end='\t')
                print(product.name, file=fm, end='\t')

                month_cart = {}
                dates_cart = {}

                if product.id in product_dict:
                    for item in product_dict[product.id]:
                        date = item[2].date()
                        if date in dates_cart:
                            dates_cart[date] += (item[0] + item[1])
                        else:
                            dates_cart[date] = item[0] + item[1]

                        month = get_year_month(item[2].date())

                        if month in month_cart:
                            month_cart[month] += (item[0] + item[1])
                        else:
                            month_cart[month] = item[0] + item[1]

                for date in dates:
                    if date in dates_cart:
                        print(round(dates_cart[date], 1), file=f, end="\t")
                    else:
                        print("", file=f, end="\t")

                print('', file=f, end='\n')

                for month in monthes:
                    if month in month_cart:
                        print(month_cart[month], file=fm, end="\t")
                    else:
                        print("", file=fm, end="\t")

                print('', file=fm, end='\n')


def run(*script_args):
    products_ids = get_product_sold_even_once_v2()
    get_cart_item(products_ids)
    get_pv(products_ids)
    get_categories(products_ids)

    get_review(products_ids)

    get_paid_count(products_ids, False, False)
    get_paid_count(products_ids, True, False)

    get_paid_count(products_ids, False, True)
    get_paid_count(products_ids, True, True)

    get_volume()
    get_volume_daily(products_ids)
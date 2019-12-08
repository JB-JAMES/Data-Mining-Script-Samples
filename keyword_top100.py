from core.models import AnalyticsCacheSearchKeywordDay
from datetime import datetime, timedelta


def get_month():

    return ["2017-10","2017-11","2017-12","2018-1","2018-2","2018-3","2018-4","2018-5","2018-6","2018-7","2018-8","2018-9","2018-10","2018-11", "2018-12"]


def run():

    day = datetime.strptime("2017-10", "%Y-%m")
    next_day = datetime.strptime("2017-11", "%Y-%m")
    last_day = datetime.strptime("2018-11", "%Y-%m")
    monthes = get_month()
    result_keyword = {}
    result_count = {}
    dict_total = {}
    idx = 1
    while day < last_day:
        keyword_caches = AnalyticsCacheSearchKeywordDay.objects.filter(theday__gte=day, theday__lt=next_day)
        date = str(day.year) + "-" + str(day.month)
        result_keyword[date] = []
        result_count[date] = []
        dict_month = {}
        for keyword in keyword_caches:

            word = keyword.keyword.replace(" ", "")
            if dict_total.get(word) is None:
                dict_total[word] = 0
            if dict_month.get(word) is None:
                dict_month[word] = 0
            dict_total[word] += keyword.total_count
            dict_month[word] += keyword.total_count

        sort_ids = sorted(dict_month, key=lambda x:dict_month[x], reverse=True)
        cnt = 0
        for id in sort_ids:
            if cnt > 99:
                break
            result_keyword[date].append(id)
            result_count[date].append(dict_month[id])
            cnt+=1

        day = datetime.strptime(monthes[idx], "%Y-%m")
        next_day = datetime.strptime(monthes[idx+1], "%Y-%m")
        idx+=1

    sorted_ids = sorted(dict_total, key=lambda x: dict_total[x], reverse=True)
    total_rank_keyword = []
    total_rank_count = []
    for id in sorted_ids:
        total_rank_keyword.append(id)
        total_rank_count.append(dict_total[id])

    with open("result.txt", "w") as f:
        monthes = get_month()
        for month in monthes:
            if month == "2018-11" or month == "2018-12":
                continue
            print(month, file=f, end='\t')
            print(" ", file=f, end='\t')
        print("합산TOP100", file=f, end='\n')
        for rank in range(0,100):
            for month in monthes:
                if month == "2018-11" or month == "2018-12":
                    continue
                if result_keyword.get(month) is None:
                    print(" ", file=f, end='\t')
                    print(" ", file=f, end='\t')
                    continue
                if len(result_keyword[month]) < rank+1:
                    print(" ", file=f, end='\t')
                    print(" ", file=f, end='\t')
                    continue
                print(result_keyword[month][rank], file=f, end='\t')
                print(result_count[month][rank], file=f, end='\t')
            print(total_rank_keyword[rank], file=f, end='\t')
            print(total_rank_count[rank], file=f, end='\n')
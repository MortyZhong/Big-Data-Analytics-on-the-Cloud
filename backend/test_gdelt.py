import json
import redis
from gdeltdoc import GdeltDoc, Filters
import pandas as pd
from datetime import datetime

# 1. 连上你队友的 Redis (测试时如果是本地没装 Redis，可以先注释掉这行)
# redis_client = redis.Redis(host='127.0.0.1', port=6379, db=0)

def fetch_gdelt_news():
    print("正在连接 GDELT 数据库...")
    
    # 2. 设置过滤器：你要找什么新闻？
    # 比如我们找包含 "Australia" 并且包含 "oil" 的新闻
    # 抛弃具体的长日期，改用 timespan 参数，只抓最近 24 小时的新闻
    f = Filters(
        keyword="Australia", # 先把关键词变宽泛一点，确保能抓到东西
        timespan="1d"        # "1d" 代表 1 day，也可以用 "1h" 代表 1小时
    )
    
    gd = GdeltDoc()
    
    try:
        # 这个操作会直接返回一个 Pandas 的 DataFrame！
        print("正在拉取新闻列表，请稍候...")
        articles_df = gd.article_search(f)
        
        if len(articles_df) == 0:
            print("没有找到符合条件的新闻。")
            return

        print(f"成功抓取 {len(articles_df)} 条新闻！开始清洗并转换格式...")
        
        for index, row in articles_df.iterrows():
            # 处理时间格式：GDELT 的时间是 '20240501T120000Z' 这种格式
            # 我们尽量转化成标准的 ISO 格式，以防 ES 报错
            raw_date = str(row['seendate'])
            try:
                parsed_date = datetime.strptime(raw_date, "%Y%m%dT%H%M%SZ").isoformat()
            except:
                parsed_date = raw_date # 如果解析失败，保留原样

            # 3. 严格按照咱们刚才定义的 gdelt_news_mapping.json 组装！
            clean_data = {
                "id": row['url'], # URL 是唯一的，直接当 ID
                "title": row['title'],
                "url": row['url'],
                "source": row['domain'],
                "created_at": parsed_date,
                "topic": "oil",
                # GDELT 的福利：它自带情感分析 (Tone)！不需要你们自己写模型算了
                "sentiment": 0.0,  # 因为这个接口没有自带情感，我们先默认填 0.0
                "country": "Australia"
            }
            
            # 打印出来看看
            print(json.dumps(clean_data, indent=2))
            print("-" * 40)
            
            # 4. 发货到 Redis (测试阶段先注释掉)
            # redis_client.lpush("incoming_gdelt", json.dumps(clean_data))
            
    except Exception as e:
        print(f"抓取失败，报错信息: {e}")

if __name__ == "__main__":
    fetch_gdelt_news()

from pyspark import SparkConf, SparkContext
from pyspark.streaming import StreamingContext
from pyspark.streaming.kafka import KafkaUtils
from kafka import SimpleProducer, KafkaClient
from kafka import KafkaProducer
from operator import add
from twitter import Twitter, OAuth, TwitterHTTPError, TwitterStream
from pyspark.sql import Row, SparkSession
from datetime import datetime, timedelta
from stop_words import get_stop_words
try:
    import json
except ImportError:
    import simplejson as json
import os
os.environ['PYSPARK_SUBMIT_ARGS'] = '--jars $SPARK_HOME/jars/spark-streaming-kafka-0-8-assembly_2.11.jar pyspark'

def getSparkSessionInstance(sparkConf):
    if ('sparkSessionSingletonInstance' not in globals()):
        globals()['sparkSessionSingletonInstance'] = SparkSession.builder.config("spark.sql.warehouse.dir", '/home/data').getOrCreate()
    return globals()['sparkSessionSingletonInstance']

def consumer():
    context = StreamingContext(sc, 30)
    dStream = KafkaUtils.createDirectStream(context, ["enf"], {"metadata.broker.list": "localhost:9092"})
    dStream.foreachRDD(task)
    context.start()
    context.awaitTermination()

def insertHashtags(hashtags, spark, time):
    if hashtags:
        rdd_hashtags = sc.parallelize(hashtags)
        rdd_hashtags = rdd_hashtags.map(lambda x: x.lower())
        if rdd_hashtags.count() > 0:
            # Convert RDD[String] to RDD[Row] to DataFrame
            ht_dataFrames = spark.createDataFrame(rdd_hashtags.map(lambda x: Row(hashtag=x, timestamp=time)))
            ht_dataFrames.createOrReplaceTempView("hashtags")
            ht_dataFrames = spark.sql("create database if not exists bdp2")
            ht_dataFrames = spark.sql("use bdp2")
            ht_dataFrames = spark.sql("select hashtag, timestamp from hashtags")
            ht_dataFrames.write.mode("append").saveAsTable("hashtags")
            print("Inserted hashtags")
    else:
        print("No hashtags avaliable to insert in hive")

def updateHashtags(spark):
    try:
        ht_dataFrames = spark.sql("select hashtag, timestamp from hashtags")
        htRDD = ht_dataFrames.rdd
        htRDD = htRDD.filter(lambda x: x["timestamp"] > datetime.now() - timedelta(minutes=60))
        ht_dataFrames = spark.createDataFrame(htRDD.map(lambda x: Row(hashtag=x["hashtag"], timestamp=["timestamp"])))
        ht_dataFrames.createOrReplaceTempView("last_htgs")
        countHtgsDataFrame = spark.sql("select hashtag, count(*) as cnt from last_htgs group by hashtag order by cnt desc")
        now = datetime.now()
        htgsDict = countHtgsDataFrame.rdd.map(lambda x: {"timestamp": now, "hashtag": x["hashtag"], "count": x["cnt"]}).take(10)
        f = open('/home/bigdataproject237/bp2/out/hashtags.txt', 'a')
        f.write(str(htgsDict))
        f.write("\n")
        f.close()
        print("Appended hashtags to file")
    except Exception as e:
        print("Exception appending hashtags " + str(e))
        pass

def insertText(text, spark, time):
    if text:
        stop_words = get_stop_words('en')
        stop_words.extend(get_stop_words('spanish'))
        stop_words.append("rt")
        rddText = sc.parallelize(text)
        rddText = rddText.flatMap(lambda x: x.split()).map(lambda x: x.lower())
        rddText = rddText.filter(lambda x: x not in stop_words)
        if rddText.count() > 0:
            # Convert RDD[String] to RDD[Row] to DataFrame
            textDataFrame = spark.createDataFrame(rddText.map(lambda x: Row(text=x, timestamp=time)))
            textDataFrame.createOrReplaceTempView("text")
            textDataFrame = spark.sql("create database if not exists bdp2")
            textDataFrame = spark.sql("use bdp2")
            textDataFrame = spark.sql("select text, timestamp from text")
            textDataFrame.write.mode("append").saveAsTable("text")
            print("Inserted text")
    else:
        print("No text avaliable to insert into hive")

def updateTexts(spark):
    try:
        textsDataFrame = spark.sql("select text, timestamp from text")
        textsRDD = textsDataFrame.rdd
        textsRDD = textsRDD.filter(lambda x: x["timestamp"] > datetime.now() - timedelta(minutes=60))
        textsDataFrame = spark.createDataFrame(textsRDD.map(lambda x: Row(text=x["text"], timestamp=["timestamp"])))
        textsDataFrame.createOrReplaceTempView("last_texts")
        countTxtsDataFrame = spark.sql("select text, count(*) as cnt from last_texts group by text order by cnt desc")
        now = datetime.now()
        textDict = countTxtsDataFrame.rdd.map(lambda x: {"timestamp": now, "text": x["text"], "count": x["cnt"]}).take(10)
        f = open('/home/bigdataproject237/bp2/out/texts.txt', 'a')
        f.write(str(textDict))
        f.write("\n")
        f.close()
        print("Appended texts to file")
    except Exception as e:
        print("Exception appending texts: " + str(e))
        pass

def insertScreenName(sn, spark, time):
    if sn:
        rddText = sc.parallelize(sn)
        if rddText.count() > 0:
            # Convert RDD[String] to RDD[Row] to DataFrame
            snDataFrame = spark.createDataFrame(rddText.map(lambda x: Row(sn=x, timestamp=time)))
            snDataFrame.createOrReplaceTempView("screennames")
            snDataFrame = spark.sql("create database if not exists bdp2")
            snDataFrame = spark.sql("use bdp2")
            snDataFrame = spark.sql("select sn, timestamp from screennames")
            snDataFrame.write.mode("append").saveAsTable("screennames")
            print("Inserted screen name")
    else:
        print("No screen name avaliable")
def updateScreenNames(spark):
    try:
        snsDataFrame = spark.sql("select sn, timestamp from screennames")
        snsRDD = snsDataFrame.rdd
        snsRDD = snsRDD.filter(lambda x: x["timestamp"] > datetime.now() - timedelta(hours=12))
        snsDataFrame = spark.createDataFrame(snsRDD.map(lambda x: Row(sn=x["sn"], timestamp=["timestamp"])))
        snsDataFrame.createOrReplaceTempView("last_sns")
        countSnDataFrame = spark.sql("select sn, count(*) as cnt from last_sns group by sn order by cnt desc")
        now = datetime.now()
        snDict = countSnDataFrame.rdd.map(lambda x: {"timestamp": now, "sn": x["sn"], "count": x["cnt"]}).take(10)
        f = open('/home/bigdataproject237/bp2/out/screennames.txt', 'a')
        f.write(str(snDict))
        f.write("\n")
        f.close()
        print("Appended screennames to file")
    except Exception as e:
        print("Exception appending screennames: " + str(e))
        pass
def insertKeywords(text, spark, time):
    if text:
        rddKeywords = sc.parallelize(text)
        rddKeywords = rddKeywords.flatMap(lambda x: x.split()).map(lambda x: x.lower())
        rddKeywords = rddKeywords.filter(lambda x: x in ["zika", "headache", "diarrhea", "flu", "ebola", "measles"])
        if rddKeywords.count() > 0:
            keywordDataFrame = spark.createDataFrame(rddKeywords.map(lambda x: Row(keyword=x, timestamp=time)))
            keywordDataFrame.createOrReplaceTempView("kwords")
            keywordDataFrame = spark.sql("create database if not exists bdp2")
            keywordDataFrame = spark.sql("use bdp2")
            keywordDataFrame = spark.sql("select keyword, timestamp from kwords")
            keywordDataFrame.write.mode("append").saveAsTable("kwords")
            print("Inserted keywords")
    else:
        print("No keywords avaliable to insert into hive")

def updateKeywords(spark):
    try:
        keywordsDataFrame = spark.sql("select keyword, timestamp from kwords")
        keywordsRDD = keywordsDataFrame.rdd
        keywordsRDD = keywordsRDD.filter(lambda x: x["timestamp"] > datetime.now() - timedelta(hours=12))
        keywordsDataFrame = spark.createDataFrame(keywordsRDD.map(lambda x: Row(keyword=x["keyword"], timestamp=["timestamp"])))
        keywordsDataFrame.createOrReplaceTempView("last_keywords")
        countKwDataFrame = spark.sql("select keyword, count(*) as cnt from last_keywords group by keyword order by cnt desc")
        now = datetime.now()
        keywordDict = countKwDataFrame.rdd.map(lambda x: {"timestamp": now, "keyword": x["keyword"], "count": x["cnt"]}).take(6)
        f = open('/home/jahnbigdata/bigdata-project2/out/keywords.txt', 'a')
        f.write(str(keywordDict))
        f.write("\n")
        f.close()
        print("Appended keywords to file")
    except Exception as e:
        print("Exception appending keywords: " + str(e))
        pass

def task(time,rdd):
    rdd = rdd.map(lambda x: json.loads(x[1]))
    records = rdd.collect() #Return a list with tweets
    spark = getSparkSessionInstance(rdd.context.getConf())

    hashtags = [element["entities"]["hashtags"] for element in records if "entities" in element]
    hashtags = [x for x in hashtags if x]
    hashtags = [element[0]["text"] for element in hashtags]
    insertHashtags(hashtags, spark, time)
    global lastHtgRefresh
    if datetime.now() > lastHtgRefresh + timedelta(minutes=10):
        updateHashtags(spark)
        lastHtgRefresh = datetime.now()

    text = [element["text"] for element in records if "text" in element]
    insertText(text, spark, time)
    global lastTxtRefresh
    if datetime.now() > lastTxtRefresh + timedelta(minutes=10):
        updateTexts(spark)
        lastTxtRefresh = datetime.now()

    sn = [element["user"]["screen_name"] for element in records if "user" in element]
    insertScreenName(sn, spark, time)
    global lastSnRefresh
    if datetime.now() > lastSnRefresh + timedelta(minutes=60):
        updateScreenNames(spark)
        lastSnRefresh = datetime.now()

    insertKeywords(text, spark, time)
    global lastKwRefresh
    if datetime.now() > lastKwRefresh + timedelta(minutes=60):
        updateKeywords(spark)
        lastKwRefresh = datetime.now()

lastHtgRefresh = None
lastTxtRefresh = None
lastSnRefresh = None
lastKwRefresh = None
if __name__ == "__main__":
    print("Starting to read tweets")
    lastHtgRefresh = datetime.now()
    lastTxtRefresh = datetime.now()
    lastSnRefresh = datetime.now()
    lastKwRefresh = datetime.now()
    print("Startup at", datetime.now())
    sc = SparkContext(appName="BigDataProject2-Roberto")
    consumer()

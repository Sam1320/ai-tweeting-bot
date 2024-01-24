import os
import modal
import shelve

bot_sdk_image = modal.Image.debian_slim(python_version="3.11").pip_install([
    "requests==2.31.0",
    "requests-oauthlib==1.3.1",
    "slack-sdk==3.26.0",
    "openai==1.3.7"
])
stub = modal.Stub("bot", image=bot_sdk_image)
volume = modal.NetworkFileSystem.persisted("tweet-storage-vol")

DATA_DIR = "/data"
TWEETS_DB = os.path.join(DATA_DIR, "tweets")
TWEET_WINDOW = 30
MODEL = "gpt-4-1106-preview"
TOPIC = "an exceptional person from any period in human history"
PROMPT = '''Give me a one-liner interesting fact about {topic}.
These are the previous facts you've mentioned:\n{tweets}\nDon't repeat yourself
and keep it short but interesting.'''
SLACK_CHANNEL = "tweets"
SLACK_MSG = "Hey peeps, I just tweeted this: {tweet}"


@stub.function(network_file_systems={DATA_DIR: volume})
def get_tweets(limit: int = TWEET_WINDOW):
    with shelve.open(TWEETS_DB) as db:
        return list(db.values())[-limit:]


@stub.function(network_file_systems={DATA_DIR: volume})
def store_tweet(tweet: str):
    from datetime import datetime
    with shelve.open(TWEETS_DB) as db:
        key = datetime.utcnow().strftime("%d/%m/%y %H:%M:%S")
        db[key] = tweet
    return key


@stub.function(secret=modal.Secret.from_name("my-openai-secret"))
def generate_tweet():
    from openai import OpenAI
    client = OpenAI()
    prev_tweets = get_tweets.remote()
    prev_tweets = "\n".join(prev_tweets)
    prompt = PROMPT.format(topic=TOPIC, tweets=prev_tweets)
    chat_completion = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    tweet = chat_completion.choices[0].message.content
    print("Prompt:", prompt)
    return tweet


@stub.function(secret=modal.Secret.from_name("my-x-secret"))
def make_tweet(tweet):
    import json
    from requests_oauthlib import OAuth1Session
    # Make the request
    oauth = OAuth1Session(
        client_key=os.environ.get("X_CONSUMER_KEY"),
        client_secret=os.environ.get("X_CONSUMER_SECRET"),
        resource_owner_key=os.environ.get("X_ACCESS_TOKEN"),
        resource_owner_secret=os.environ.get("X_ACCESS_TOKEN_SECRET"),
    )
    # Making the request
    resp = oauth.post("https://api.twitter.com/2/tweets", json={"text": tweet})
    if resp.status_code != 201:
        raise ValueError(f"Request error: {resp.status_code} {resp.text}")
    # Print the response for debugging
    print(json.dumps(resp.json(), indent=4, sort_keys=True))


@stub.function(secret=modal.Secret.from_name("my-slack-secret"))
def send_message(channel, message):
    import slack_sdk
    client = slack_sdk.WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    client.chat_postMessage(channel=channel, text=message)


@stub.function(schedule=modal.Period(days=1))
def daily_routine():
    print("generating tweet...")
    tweet = generate_tweet.remote()
    print("storing tweet...")
    store_tweet.remote(tweet)
    print("sending tweet...")
    make_tweet.remote(tweet)
    print("sending slack message...")
    send_message.remote(SLACK_CHANNEL, SLACK_MSG.format(tweet=tweet))
    print("done :).")

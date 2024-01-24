# AI Tweeting Bot
AI bot that tweets once a day about a given topic and posts the tweet to a slack channel.

The bot is deployed on Modal and uses OpenAI's api to generate the tweet.

All in less than 100 lines of code and with a budget of $0.00 :D.

## Setup
1. Setup a [modal](https://modal.com/) account.
2. Setup a [free X account](https://developer.twitter.com/en/portal/petition/essential/basic-info) and get the keys (consumer_key, consumer_secret, access_token, access_token_secret). This [repo](https://github.com/twitterdev/Twitter-API-v2-sample-code/tree/main) is also useful here.
4. Setup an [OpenAI account](https://platform.openai.com/signup) and get the api key.
5. [Optional]: Setup a (slack app)[https://api.slack.com/tutorials/tracks/getting-a-token] and get a bot token.
6. Add the all the keys in the [modal secrets](https://modal.com/docs/guide/secrets) dashboard and name them as follows:
    -  OpenAI api key: `OPENAI_API_KEY` in the `my-openai-secret` namespace.
    - X keys:  (all in the `my-x-secret` namespace)
        - consumer_key: `X_CONSUMER_KEY` 
        - consumer_secret: `X_CONSUMER_SECRET`
        - access_token: `X_ACCESS_TOKEN`
        - access_token_secret: `X_ACCESS_TOKEN_SECRET`
    - Slack bot token: `SLACK_BOT_TOKEN` in the `my-slack-secret` namespace.
7. Modify the global parameters `TWEET_WINDOW`, `MODEL`, `PROMPT`, `TOPIC`, `SLACK_CHANNEL` and `SLACK_MSG` as you prefer. Just make sure that the `PROMPT` still has variables {tweets} and {topic} in it.
## Usage
Just clone this repo, install the requirements, run `modal deploy` and you are good to go. You can then go to modal.com/apps and see your deployed app. You can also run `modal logs` to see the logs of your app.

## Code
First we import basic global dependencies and setup the [image](https://modal.com/docs/reference/modal.Image) that the bot will run on. We just need a simple debian image with python 3.11 and the required dependencies.
```python
import os
import modal
import shelve
bot_sdk_image = modal.Image.debian_slim(python_version="3.11").pip_install([
    "requests==2.31.0",
    "requests-oauthlib==1.3.1",
    "slack-sdk==3.26.0",
    "openai==1.3.7"
])
```

We also define a [stub](https://modal.com/docs/reference/modal.Stub) to decorate our functions so they can be run in a container using the image specified above.
```python
stub = modal.Stub("bot", image=bot_sdk_image)
```

Then we define a [volume](https://modal.com/docs/guide/network-file-systems) to store the tweets so we can keep track of them and not repeat them. Note that this is only necessary because the free X account only allows to create tweets and not to read them. If you have a paid account you can just read the tweets from the timeline and not need to store them. Nevertheless, this is a good opportunity to show how to use volumes in modal. Note that the volume is persisted so the tweets will still be there even if the app is stopped.

```python
volume = modal.NetworkFileSystem.persisted("tweet-storage-vol")
```

The `DATA_DIR` path will be mapped to the volume (NetworkFileSystem) `tweet-storage-vol`. And the `TWEETS_DB` is where we will store the tweets in the volume.

```python
DATA_DIR = "/data"
TWEETS_DB = os.path.join(DATA_DIR, "tweets")
```

Define the global parameters. If you don't want to send messages to slack just remove the `SLACK_CHANNEL` and `SLACK_MSG` parameters. 

(We could move these params to their own config file but there is something *satifying* about having everything in one short file :D).
```python
TWEET_WINDOW = 30
MODEL = "gpt-4-1106-preview"
TOPIC = "an exceptional person from any period in human history"
PROMPT = '''Give me a one-liner interesting fact about {topic}.
These are the previous facts you've mentioned:\n{tweets}\nDon't repeat yourself
and keep it short but interesting.'''
SLACK_CHANNEL = "tweets"
SLACK_MSG = "Hey peeps, I just tweeted this: {tweet}"
```

Now we define the functions to store and fetch the last `TWEET_WINDOW` tweets. We'll use the date&time as key so we can fetch tweets from specific time intervals if needed. Note how we map the `DATA_DIR` path to the volume we defined above in the `stub.function` decorator. 

```python
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
```


This is the function that will create the tweet. It injects previous tweets into the prompt and makes the call to the OpenAI api. Note that if the `TWEET_WINDOW` is too big the prompt might exceed the max context window. In that case you can just reduce the `TWEET_WINDOW` or use a different model with longer context windows.

```python
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
```

Finally we define the function that will post the tweet to X. (If you have a paid X dev account can find [this and other examples](https://github.com/twitterdev/Twitter-API-v2-sample-code/blob/main/Manage-Tweets/create_tweet.py) useful).

The last line just prints the response so you can check what happened in case of an error. You can check the logs of any given function by going into `modal.com/apps`, clicking on the function name, and clicking on the logs tab for any given execution.

```python
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
```

Optionally, we post the tweet to the given slack channel. 

(Something cool about connecting the bot to slack is that we can also use it to send messages to the bot and dynamically change the topic of the tweets or just give the bot feedback!)

```python
@stub.function(secret=modal.Secret.from_name("my-slack-secret"))
def send_message(channel, message):
    import slack_sdk
    client = slack_sdk.WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    client.chat_postMessage(channel=channel, text=message)
```

With all the required functions ready we can now define the main function that will be run once a day.

```python
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
```

And voilà! We just created a bot that will tweet once a day about any given topic and inform you in your preferred slack channel, all in less than 100 lines of code and with a budget of $0.00. You can now run `modal deploy` and see your bot in action.
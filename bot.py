import os
import modal
import shelve

harry_sdk_image = modal.Image.debian_slim(python_version="3.11").pip_install([
    "requests==2.31.0",
    "requests-oauthlib==1.3.1",
    "slack-sdk==3.26.0",
    "openai==1.3.7"
])

stub = modal.Stub("harry", image=harry_sdk_image)

DATA_DIR = "/data"
TWEETS_DB = os.path.join(DATA_DIR, "tweets")
volume = modal.NetworkFileSystem.persisted("tweet-storage-vol")


@stub.function(network_file_systems={DATA_DIR: volume})
def store_tweet(tweet: str):
    from datetime import datetime
    with shelve.open(TWEETS_DB) as db:
        key = datetime.utcnow().strftime("%d/%m/%y %H:%M:%S")
        db[key] = tweet
    return key


@stub.function(network_file_systems={DATA_DIR: volume})
def get_tweet(key: str):
    with shelve.open(TWEETS_DB) as db:
        return db[key]


@stub.function(network_file_systems={DATA_DIR: volume})
def get_tweets():
    with shelve.open(TWEETS_DB) as db:
        return list(db.values())


@stub.function(network_file_systems={DATA_DIR: volume})
def delete_tweets():
    with shelve.open(TWEETS_DB) as db:
        db.clear()
    return "Deleted all tweets"


@stub.function(secret=modal.Secret.from_name("my-slack-secret"))
def send_message(channel, message):
    import slack_sdk
    client = slack_sdk.WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    client.chat_postMessage(channel=channel, text=message)


@stub.function(secret=modal.Secret.from_name("my-openai-secret"))
def generate_tweet():
    from openai import OpenAI
    client = OpenAI()
    previous_facts = get_tweets.remote()
    previous_facts = "\n".join(previous_facts)
    prompt = \
        "Give me a one-liner interesting fact about a random scientist/philosopher."\
        f"Pick a fact which is not already one of these:\n\n{previous_facts}"
    chat_completion = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    tweet = chat_completion.choices[0].message.content
    print("Prompt:", prompt)
    return tweet


@stub.function(secret=modal.Secret.from_name("my-x-secret"))
def make_tweet(tweet):
    from requests_oauthlib import OAuth1Session
    import json
    """Makes a tweet using the Twitter API.

    Args:
        tweet (str): The text of the tweet to be made.

    Returns:
        str: The text of the tweet that was made.
    """
    consumer_key = os.environ.get("X_CONSUMER_KEY")
    consumer_secret = os.environ.get("X_CONSUMER_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET")

    payload = {"text": tweet}
    # Make the request
    oauth = OAuth1Session(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=access_token,
        resource_owner_secret=access_token_secret,
    )

    # Making the request
    response = oauth.post(
        "https://api.twitter.com/2/tweets",
        json=payload,
    )

    if response.status_code != 201:
        raise ValueError(
            "Request returned an error: "
            f"{response.status_code} {response.text}"
        )

    print(f"Response code: {response.status_code}")

    # Saving the response as JSON
    json_response = response.json()
    print(json.dumps(json_response, indent=4, sort_keys=True))


tweets = [
    "Knowledge can be communicated, but not Wisdom. One can live by it, be fortified by it, do wonders through it,  but one cannot communicate and teach it. Hermann Hesse.",
    "Wealth consists not in having great possessions, but in having few wants. Epictetus."
]


# @stub.local_entrypoint()
# def main():
    # store_tweet.remote("Rosalind Franklin, an English chemist, played a crucial role in the discovery of the structure of DNA but her contribution was overlooked until after her death.")
    # print(get_tweets.remote())
    # delete_tweets.remote()
    # print("generating tweet...")
    # tweet = generate_tweet.remote()
    # print("storing tweet...")
    # store_tweet.remote(tweet)
    # print("sending tweet...")
    # make_tweet.remote(tweet)
    # print("sending slack message...")
    # channel = "having-a-lovely-home"
    # message = f"Hey fam, I just tweeted this: {tweet}"
    # send_message.remote(channel, message)
    # print("done")

@stub.function(schedule=modal.Period(days=1))
def daily_routine():
    print("generating tweet...")
    tweet = generate_tweet.remote()
    print("storing tweet...")
    store_tweet.remote(tweet)
    print("sending tweet...")
    make_tweet.remote(tweet)
    print("sending slack message...")
    channel = "having-a-lovely-home"
    message = f"Hey fam, I just tweeted this: {tweet}"
    send_message.remote(channel, message)
    print("done")



# @stub.function(schedule=modal.Period(days=1))
# def daily_greeting():
#     channel = "having-a-lovely-home"
#     message = "Good morning! ^.^ "
#     send_message.remote(channel, message)


# @stub.function(schedule=modal.Period(days=1))
# def daily_tweet():
#     tweet = tweets[0]
#     make_tweet.remote(tweet)

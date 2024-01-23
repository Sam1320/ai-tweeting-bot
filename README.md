# AI Tweeting Bot
Simple bot that tweets once a day given a prompt and posts the tweet to a slack channel.

The bot is deployed on Modal and uses OpenAI's api to generate the tweet.

## Setup
1. Setup a [modal](https://modal.com/) account.
2. Setup a [free X account](https://developer.twitter.com/en/portal/petition/essential/basic-info) and get the keys (consumer_key, consumer_secret, access_token, access_token_secret)
4. Setup an [OpenAI account](https://platform.openai.com/signup) and get the api key.
5. [Optional]: Setup a (slack app)[https://api.slack.com/tutorials/tracks/getting-a-token] and get a bot token.
6. Add the all the keys in the [modal secrets](https://modal.com/docs/guide/secrets) dashboard as described below.
`my-openai-secret` - OpenAI api key.
`my-X-secret` - consumer_key, consumer_secret, access_token, access_token_secret.
`my-slack-secret` - slack bot token.
## Usage
Just clone this repo, install the requirements, run `modal deploy` and you are good to go. You can then go to modal.com/apps and see your deployed app. You can also run `modal logs` to see the logs of your app




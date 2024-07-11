# pigpt

## Prepare

```shell
# install ngrok, if not already
brew install ngrok/ngrok/ngrok

# install pipx, if not already
brew install pipx && pipx ensurepath

# install poetry, if not already
pipx install poetry
```

## Install

```shell
# create ngron config, ensure <auth token> is updated
cp ngrok.dist.yml ngrok.yml

# start ngrok app
ngrok --config=ngrok.yml start pigpt

# install project dependencies
poetry install

# create slack app manifest, ensure <ngrok domain> is updated
cp slack.dist.yml slack.yml

# create a list of devices
cp devices.dist.json devices.json

# create a .env file, ensure OPENAI_* and SLACK_* variables are updated
cp .env.dist .env

# during development, turn off GPIO ops
echo MOCK_GPIO=true >> .env

# start the web server
poetry run gunicorn pigpt.web:app
```

# Usage

Go to Slack and chat with `PiGPT` application.

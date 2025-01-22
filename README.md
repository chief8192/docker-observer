# docker-observer

Docker container for monitoring the status changes of other containers.

## Building

```shell
$ sudo docker build --tag "chief8192/docker-observer" .
```

## Configuring

Configuration is done by way of a `config.json` file with the following format:

```json
{
  "pushover_app_token": "",
  "pushover_user_key": ""
}
```

### Configuration properties

| Property             | Required | Description                                                                         |
| -------------------- | -------- | ----------------------------------------------------------------------------------- |
| `pushover_app_token` | No       | [Pushover](https://pushover.net/) app token to use when sending push notifications. |
| `pushover_user_key`  | No       | [Pushover](https://pushover.net/) user key to use when sending push notifications.  |

## Running

```shell
$ sudo docker run \
    --detach \
    --name="docker-observer" \
    --network="host" \
    --restart="always" \
    --volume="${PWD}/config.json:/config.json" \
    --volume="/var/run/docker.sock:/var/run/docker.sock" \
    "chief8192/docker-observer:latest"
```

#!/bin/bash
xhost +local:docker
cd docker || exit 1

# 檢查 Docker image 是否存在，若不存在則進行 build
if [[ "$(docker images -q locobot_humble_dev 2> /dev/null)" == "" ]]; then
    echo "Image not found. Building docker image..."
    docker compose -f docker-compose.locobot.yml build
else
    echo "Image found. Skipping build."
fi

# 檢查 Container 是否已經在執行，如果沒有就用 up -d 啟動在背景，如果已啟動就直接 exec 進去
if [ "$(docker ps -q -f name=locobot_humble_dev)" ]; then
    echo "Container is running. Executing bash..."
    docker exec -it locobot_humble_dev /bin/bash
else
    echo "Starting container and executing bash..."
    docker compose -f docker-compose.locobot.yml up -d
    docker exec -it locobot_humble_dev /bin/bash
fi


docker build - build image from dockerfile
docker run - create and run a new container from image
docker start - start one or more stopped containers
docker rename - rename container
docker stop - stop container
docker rm - remove container

docker container - manage containers

docker image - manage images


Reset routes:
    localhost:500x/__reset (POST)

Adminer:
    Server (auth DB): mysql
    Username: auth_user
    Password: auth_password
    Database: auth_db
    or
    Server (store DB): store-mysql
    Username: store_user
    Password: store_password
    Database: store_db
    Root also exists for both DB containers:
    Username: root
    Password: rootpassword
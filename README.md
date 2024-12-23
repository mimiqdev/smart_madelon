# Smart Madelon

迈迪龙新风接入Home Assistant解决方案

## Prerequisite
Home Assistant
HACS

## Datasheets
![Datasheets](assets/datasheets.jpg)

## Hardware Dependencies
RS485转WIFI模块 接在新风面板后面

Example:
汉枫的模块

### Usage
网线插设备网口，另外一头剪掉，里面有8根网线，标准网线的话，找到5 6 7 8这4根线（蓝白，绿，棕白，棕），然后7 8接电源正负极，5~36V稳定电源，7正8负，5 6接485的AB，5A6B

## HACS Custom Integration
### Features
- A Fan entity with speed control
- Two sensors for temperature and humidity
Other features like mode control and timer control will be added in future

### Setup guide

Add Custom Repo from HACS:
![Step 1](assets/step1.png)

Put this repo url into config:
![Step 2](assets/step2.png)

Download integration, then add integration:
![Step 3](assets/step3.png)

Config your RS485 Module IP address:
![Step 4](assets/step4.png)

You will find 3 new entities:
![Result](assets/result.png)

## TODO list

- [x]Home Assistant Custom Integration
- [ ]Separate supply air and exhaust air speed control
- [ ]Support timer feature
- [ ]Add more stats as sensors and switches


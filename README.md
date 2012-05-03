# antigfw #

## 项目目的 ##
启动uniproxy和ssh，互相连接，形成自动翻墙系统。

## 配置 ##

* logfile: 记录到哪个日志文件。
* pidfile: pid文件。
* servers: 一个列表，每个元素记录一个服务器的配置。
  * proxyport: 代理的本地工作端口，即"socksv5"端口。
  * username: 登录ssh服务器的用户名。
  * sshhost: 代理服务器主机名。
  * sshport: 代理服务器端口名。
  * sshprivfile: 代理服务器私钥文件路径。
* uniproxy: 是否启动uniproxy。

# uniproxy #

## 项目目的 ##
替换squid，做一个轻量级的代理系统，用于翻墙。

## 依赖 ##
系统基于python-gevent，而该包基于python-greenlet和libevent。注意：greenlet0.3.2在i386环境下有一个已知bug会导致段错误，请使用该版本的人自行升级。

## 工作流程 ##
假定有一个或多个ssh或者同类型socksv5代理在工作，在此之上做一个http代理，让其他程序使用，达到以下目的：

1. 自动分流，只有特定的域名才进行翻墙。
2. 支持CONNECT模式，可以用于https翻墙。
3. 负载均衡，每个upstream服务器尽量均衡访问，并可以设定最高上限。

## 配置 ##
默认绑定到本地的8118端口，使用gfw作为滤表文件名。
向命令行传入配置文件路径可以加载一个到多个配置文件，配置文件为python格式，其中可以定义以下变量：

* logfile: 记录到哪个日志文件
* localip: 绑定到哪个IP，默认0.0.0.0。
* localport: 绑定到哪个端口，默认8118。
* socks: 一个列表，每个元素为(addr, port, max_conn)，指名一个socksv5代理的地址，端口，最大连接。
  默认[('127.0.0.1', 7777, 10),]。
* filter: 一个列表，每个元素都是字符串，表示滤表文件名。默认gfw。
* max_conn: 用于自动配置socks中的max_conn默认值。

## 自动配置 ##

* socks: 当socks=None，并且servers有配置的时候，会自动为每个server产生一条socks记录。

# Issus #

## lintian ##
W: antigfw source: diff-contains-git-control-dir .git
W: antigfw: init.d-script-uses-usr-interpreter etc/init.d/antigfw /usr/bin/python

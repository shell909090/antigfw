# 简述 #

## 目标 ##
一体化的自动翻墙工具，为多人共享一到两个翻墙帐号，实现流畅的翻墙而作。
系统分为两个部分，uniproxy和antigfw。antigfw是一套配置-启动-监管脚本，用于启动和管理ssh以及uniproxy。uniproxy负责实施代理分流，将需要代理和不需要代理的流量分离开。

## HOWTO ##

1. 安装python-gevent和openssh-client包，并且有一个以上可以用于翻墙的ssh帐号。
2. 在翻墙帐号上设定密钥而非密码(将你的公钥导出到~/.ssh/authorized_keys文件，具体参照[Linux](http://blog.yening.cn/2006/10/30/187.html)和[Windows](http://butian.org/knowledge/linux/1632.html))。
3. 设定/etc/default/antigfw文件，修改其中的servers记录。
4. 完成修改后，将上述配置中的daemon由False改为True。
5. 用/etc/init.d/antigfw restart重启服务。
6. 在浏览器上设定服务器的8118端口为代理，类型为http代理，如：192.168.1.8:8118(其中192.168.1.8为你启动antigfw服务的机器IP)。
7. 如果有iptables防火墙，又需要对外服务，开放8118端口。(参考：-A INPUT -p tcp -m tcp --dport 8118 -j ACCEPT)

## 管理 ##
如果某个域名需要被添加到翻墙列表中，修改/etc/uniproxy/gfw，一行一条记录，然后访问[http://192.168.1.8:8118/load](http://192.168.1.8:8118/load)。系统会重新读取gfw文件。另外，欢迎将你的gfw文件的补丁发送给我。
如果你想要看ssh代理的使用状况，当前有多少页面正在处理，可以访问[http://192.168.1.8:8118/stat](http://192.168.1.8:8118/stat)。
如果你想要关闭uniproxy，可以访问[http://192.168.1.8:8118/stat](http://192.168.1.8:8118/stat)。如果是由antigfw监控uniproxy启动的，uniproxy会自动重启。
如果不想打包重装，又想获得最新的gfw列表，可以执行gfw_tester -d。将标准输出定位到/etc/uniproxy/gfw。*注意：这会覆盖你原本的gfw列表配置。*

# antigfw #

## 项目目的 ##
启动uniproxy和ssh，互相连接，形成自动翻墙系统。

## 配置 ##

* logfile: 记录到哪个日志文件。
* daemon: 是否启动服务程序，用于暂停服务，阻止软件包刚刚完成安装后服务立刻启动导致的配置错误
* pidfile: pid文件。
* servers: 一个列表，每个元素记录一个服务器的配置。
  * sockport: 代理的本地工作端口，即"socksv5"端口。整型。
  * listenport: 转发模式的代理端口，一般是http端口。整型，格式为(本地端口,远程端口)。注意远程ip是localhost。
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

* logfile: 记录到哪个日志文件。
* loglevel: 记录级别，默认WARNING。
* localip: 绑定到哪个IP，默认0.0.0.0。
* localport: 绑定到哪个端口，默认8118。
* socks: 一个列表，每个元素为(type, addr, port, max_conn)，指名一个socksv5代理的类型地址，端口，最大连接。类型目前可以是socks5，预定加入http。
* filter: 一个列表，每个元素都是字符串，表示滤表文件名。默认gfw。

## 自动配置 ##

* socks: 当socks=None，并且servers有配置的时候，会自动为每个server产生一条socks记录。
* max\_conn: 用于自动配置socks中的max\_conn默认值。

## gfw_tester ##
用于自动测试gfw文件中的域名是否被墙。

	gfw_tester [-f] gfw [-d]

* -f: 直接在文件上进行过滤，所有可以访问的域名会被自动删除。
* -d: 无视gfw参数，直接下载网络上的最新gfw列表，在stdout中输出。

注意：这个测试程序只测试首页是否连通，因此有很多网站可能无法发现被墙，从而导致误删。例如google.com。

# Issus #

## bug report ##
有问题可以向项目主页[http://github.com/shell909090/antigfw](http://github.com/shell909090/antigfw)提交issus，或者向[我的邮箱](mailto:shell909090@gmail.com)发送信件。

## lintian ##
> W: antigfw source: diff-contains-git-control-dir .git
> W: antigfw: init.d-script-uses-usr-interpreter etc/init.d/antigfw /usr/bin/python

# 简述 #

## 目标 ##

一体化的自动翻墙工具，为多人共享一到两个翻墙帐号，实现流畅的翻墙而作。

系统分为两个部分，uniproxy和antigfw。antigfw是一套配置-启动-监管脚本，用于启动和管理ssh以及uniproxy。uniproxy负责实施代理分流，将需要代理和不需要代理的流量分离开。

## 管理 ##

如果你想要看ssh代理的使用状况，当前有多少页面正在处理，可以访问[http://localhost:8118/](http://localhost:8118/)。

# 安装 #

## python安装方法 ##

antigfw包含两个部分，python安装方法能安装的仅有uniproxy而已。antigfw的程序主体是一套debian打包脚本，因此无法通过python方式安装。

	python setup.py install

注意，如果需要向系统内安装，你需要sudo。

### 启动程序 ###

你需要准备一个antigfw.conf，就像uniproxy目录中提供的那样。

随后，你可以到uniproxy的安装目录中，使用以下指令启动uniproxy。configure是配置文件的路径。

	python main.py configure

## deb打包安装 ##

### deb打包 ###

deb打包能够同时安装antigfw和uniproxy，比较简单的打包方法如下。最简单的打包方法，是在setup.py的目录下，执行debuild。注意，这需要你在系统中安装了devscripts包。

如果你希望打出比较干净的包，可以用pbuilder或cowbuilder。具体使用方法不展开。

### deb包安装 ###

deb包安装比较简单，使用以下指令即可。

	dpkg -i antigfw_xxx.deb

具体文件名看你打出来的包叫什么。如果当前用户没有系统权限，你可能需要使用sudo。

## 系统配置 ##

1. 安装python-gevent和openssh-client包，并且有一个以上可以用于翻墙的ssh帐号。
2. 在翻墙帐号上设定密钥而非密码(将你的公钥导出到~/.ssh/authorized_keys文件，具体参照[Linux](http://blog.yening.cn/2006/10/30/187.html)和[Windows](http://butian.org/knowledge/linux/1632.html))。
3. 设定/etc/default/antigfw文件，修改其中的sshs记录。
4. 完成修改后，将上述配置中的daemon由False改为True。
5. 用/etc/init.d/antigfw restart重启服务。
6. 在浏览器上设定服务器的8118端口为代理，类型为http代理，如：localhost:8118(其中localhost为你启动antigfw服务的机器IP)。
7. 如果有iptables防火墙，又需要对外服务，开放8118端口。(参考：-A INPUT -p tcp -m tcp --dport 8118 -j ACCEPT)

# antigfw #

## 项目目的 ##

启动uniproxy和ssh，互相连接，形成自动翻墙系统。

## 全局配置 ##

* logfile: 记录到哪个日志文件。
* loglevel: 记录级别，默认WARNING。
* daemon: 是否启动服务程序，用于暂停服务，阻止软件包刚刚完成安装后服务立刻启动导致的配置错误
* pidfile: pid文件。

## ssh配置 ##

* autossh: 控制ssh启动管理是否生效
* sshs: 一个列表，每个元素记录一个服务器的配置。
  * sockport: 代理的本地工作端口，即"socksv5"端口。整型。
  * listenport: 转发模式的代理端口，一般是http端口。整型，格式为(本地端口,远程端口)。注意远程ip是localhost。
  * username: 登录ssh服务器的用户名。
  * sshhost: 代理服务器主机名。
  * sshport: 代理服务器端口名。
  * sshprivfile: 代理服务器私钥文件路径。

# uniproxy #

## 项目目的 ##

替换squid，做一个轻量级的代理系统，用于翻墙。

## 依赖 ##

* python-gevent。该包基于python-greenlet和libevent。注意：greenlet0.3.2在i386环境下有一个已知bug会导致段错误，请使用该版本的人自行升级。

## 工作流程 ##

假定有一个或多个ssh或者同类型socksv5代理在工作，在此之上做一个http代理，让其他程序使用，达到以下目的：

1. 自动分流，只有特定的域名才进行翻墙。内置了三套机制来分析是否需要翻墙。
  1. 域名分析模式，当域名匹配到域名列表，则翻墙。
  2. 白名单模式，当域名的IP在白名单地址表中，则翻墙。
  3. 黑名单模式，当域名的IP不在黑名单地址表中，则翻墙。
2. 支持CONNECT模式，可以用于https翻墙。
3. 负载均衡，每个upstream服务器尽量均衡访问，并可以设定最高上限。

默认模式是域名+黑名单混合。域名内放置常用域名列表，黑名单是来自[chnroutes](https://github.com/fivesheep/chnroutes)的IP列表。凡是非中国IP，一概翻墙。这会引入另一个问题，即，对于某些智能DNS，它会引导你访问国外站点而非国内站点。

另外，在dnsproxy模式下会打开dns代理服务。这个服务会使用uniproxy内置的代理服务群，以tcp方式转发udp的dns请求，从而避免dns劫持和污染。你可以仅将DNS服务器设定到本机，而不用uniproxy代理所有请求。

## 基本配置 ##

默认绑定到本地的8118端口。向命令行传入配置文件路径可以加载一个到多个配置文件，配置文件为python格式，其中可以定义以下变量：

* logfile: 记录到哪个日志文件。
* loglevel: 记录级别，默认WARNING。
* uniproxy: 是否启动uniproxy。
* localip: 绑定到哪个IP，默认0.0.0.0。
* localport: 绑定到哪个端口，默认8118。
* managers: 一个dict，用户名为key，密码为value。如果为None或者为空则不验证。
* users: 一个dict，用户名为key，密码为value。如果为None或者为空则不验证。

## 代理配置 ##

* max_conn: 默认最大可连接数。如果设定为0，则sshs到proxy的自动转换不生效。
* proxy: 一个列表，每个元素为一个字典，指名一个代理。
  * type: 类型目前可以是socks5,http。
  * ssl: 是否需要ssl连接，默认为False。
  * addr: 服务器地址。
  * port: 端口。
  * max\_conn: 最大可连接数。
  * name: 显示名。
  * username: 连接用户名。
  * password: 密码。
  * rdns: 是否使用dns解析域名。

## 过滤配置 ##

* whitenets: 翻墙白名单，一个列表，每个元素都是字符串，表示NetFilter文件名。
  当DNS解析后的结果在此IP范围内，会启用代理。None不启用。
* blacknets: 翻墙黑名单，一个列表，每个元素都是字符串，表示NetFilter文件名。
  当启用后，DNS解析结果不在此IP范围内，会启用代理。None不启用。
* upstream: 对于满足翻墙的请求，可以转交给upstream处理。
  一般此处会填写HttpOverHttp或者GAE的实例。

## DNS配置 ##

* dnsserver: 一个DNS服务器名，代理在需要DNS查询时会使用这个DNS作为默认DNS。
* dnscache: DNS缓存大小，默认为512。
* dnsproxy: 控制是否打开dnsproxy。
* dnsport: 打开的dnsport在哪个端口。
* dnsfake: 假dns结果的列表。
* dnstimeout: dns超时时间，如果一直没有结果返回，就出错

## NetFilter ##

IP地址过滤系统，主要是whitenets和blacknets上使用。具体格式为，文本格式，回车分割，每行一个地址段。第一部分的内容是IP，第二部分是mask。允许以下两种格式。

* ip mask: 例如39.64.0.0 255.224.0.0
* ip/mask: 39.64.0.0/11

对上述文本格式进行gzip压缩，即可以得到ip地址过滤文件。通常建议的配置方法是利用chnroutes项目生成中国地址池，然后转换为netfilter格式，再gzip压缩即可。

## 自动配置 ##

* socks: 当max_conn不为0，并且sshs有配置的时候，会自动为每个sshs产生一条proxy记录。
* max\_conn: 用于自动配置socks中的max\_conn默认值。

## dns2tcp ##

在53端口上运行一个dns服务器，将请求以tcp方式转发到远程服务器上（默认8.8.8.8）。由于gfw只对udp包进行污染，因此可以避免dns污染问题。

但是，由于仅仅做了udp-tcp转换，而没有任何加密。因此无法保证内容不被拦截和替换。

# Issus #

## bug report ##

有问题可以向项目主页[http://github.com/shell909090/antigfw](http://github.com/shell909090/antigfw)提交issus，或者向[我的邮箱](mailto:shell909090@gmail.com)发送信件。

## lintian ##

	W: antigfw source: diff-contains-git-control-dir .git
	W: antigfw: init.d-script-uses-usr-interpreter etc/init.d/antigfw /usr/bin/python

## TODO ##

* http上游代理支持完成，不过还没测试
* 增加ssh密钥管理形式

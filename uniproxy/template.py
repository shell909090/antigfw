#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2010-09-27
@author: shell.xu
'''
import os

class TemplateCode(object):
    def __init__(self): self.deep, self.rslt, self.defs = 0, [], []

    def str(self, s):
        if s: self.rslt.append(u'%swrite(u\'\'\'%s\'\'\')' % (u'\t' * self.deep, s))

    def code(self, s):
        r = self.map_code(s)
        if r: self.rslt.append(r)
    def map_code(self, s):
        s, tab = s.strip(), self.deep
        if s.startswith(u'='): s = u'write(%s)' % s[1:]
        elif s.startswith(u'end'):
            self.deep -= 1
            return
        elif s.startswith(u'for') or s.startswith(u'if'): self.deep += 1
        elif s.startswith(u'el'): tab -= 1
        elif s.startswith(u'def'):
            self.defs.append(s + u'\n')
            return
        elif s.startswith(u'include'):
            self.include(s[8:])
            return
        elif s.startswith(u'import'):
            self.defs.append(s + u'\n')
            return 
        return u'%s%s' % (u'\t' * tab, s)

    def include(self, filepath):
        with open(filepath, 'r') as tfile:
            self.process(tfile.read().decode('utf-8'))

    def process(self, s):
        while True:
            i = s.partition(u'{%')
            if not i[1]: break
            if i[0].strip(): self.str(i[0])
            t = i[2].partition(u'%}')
            if not t[1]: raise Exception('not match')
            self.code(t[0])
            s = t[2]
        self.str(s)

    def get_code(self): return u'\n'.join(self.rslt)

class Template(object):
    '''
    模板对象，用于生成模板
    代码：
        info = {'r': r, 'objs': [(1, 2), (3, 4)]}
        response.append_body(tpl.render(info))
    模板：
        <html><head><title>{%=r.get('a', 'this is title')%}</title></head>
        <body><table><tr><td>col1</td><td>col2</td></tr>
        {%for i in objs:%}<tr><td>{%=i[0]%}</td><td>{%=i[1]%}</td></tr>{%end%}
        </table></body></html>
    '''
    def __init__(self, filepath = None, template = None, env = None):
        '''
        @param filepath: 文件路径，直接从文件中load
        @param template: 字符串，直接编译字符串
        '''
        if not env: env = globals()
        self.tc, self.env = TemplateCode(), env
        if filepath: self.loadfile(filepath)
        elif template: self.loadstr(template)

    def loadfile(self, filepath):
        ''' 从文件中读取字符串编译 '''
        self.modify_time = os.stat(filepath).st_mtime
        self.tc = TemplateCode()
        with open(filepath, 'r') as tfile: self.loadstr(tfile.read())
    def loadstr(self, template):
        ''' 编译字符串成为可执行的内容 '''
        if isinstance(template, str): template = template.decode('utf-8')
        self.tc.process(template)
        self.htmlcode, self.defcodes = compile(self.tc.get_code(), '', 'exec'), {}
        for i in self.tc.defs:
            eval(compile(i, '', 'exec'), self.env, self.defcodes)
    def reload(self, filepath):
        ''' 如果读取文件，测试文件是否更新。 '''
        if not hasattr(self, 'modify_time') or \
                os.stat(filepath).st_mtime > self.modify_time:
            self.loadfile(filepath)

    def render(self, kargs):
        ''' 根据参数渲染模板 '''
        b = []
        kargs['write'] = lambda x: b.append(unicode(x))
        eval(self.htmlcode, self.defcodes, kargs)
        return u''.join(b)

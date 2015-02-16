import os
import re
from itertools import chain
from zhconv import convert as zhconv

halfwidth = frozenset('!(),:;?')
fullwidth = frozenset(chain(
	range(0xFF02, 0xFF07+1),
	(0xFF0A, 0xFF0B, 0xFF0E, 0xFF0F, 0xFF1C, 0xFF1D, 0xFF1E, 0xFF3C, 0xFF3E, 0xFF3F, 0xFF40),
	range(0xFF10, 0xFF19+1),
	range(0xFF20, 0xFF3A+1),
	range(0xFF41, 0xFF5A+1)))
resentencesp = re.compile('([.﹒﹔﹖﹗．；。！？]["’”」』]{0,2}|：(?=["‘“「『]{1,2}|$))')
refixmissing = re.compile('(^[^"‘“「『’”」』，；。！？]+["’”」』]|^["‘“「『]?[^"‘“「『’”」』]+[，；。！？][^"‘“「『‘“「『]*["’”」』])(?!["‘“「『’”」』，；。！？])')

punctstr = (
	'!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~¢£¥·ˇˉ―‖‘’“”•′‵、。々'
	'〈〉《》「」『』【】〔〕〖〗〝〞︰︱︳︴︵︶︷︸︹︺︻︼︽︾︿﹀﹁﹂﹃﹄'
	'﹏﹐﹒﹔﹕﹖﹗﹙﹚﹛﹜﹝﹞！（），．：；？［｛｜｝～､￠￡￥')

punct = frozenset(punctstr)

resplitpunct = re.compile('([%s])' % re.escape(punctstr))

tailpunct = ('''\t\n\x0b\x0c\r !),-.:;?]}¢·ˇˉ―‖’”•′■□△○●\u3000'''
             '''、。々〉》」』】〕〗〞︰︱︳︴︶︸︺︼︾﹀﹂﹄﹏'''
             '''﹐﹒﹔﹕﹖﹗﹚﹜﹞！），．：；？｜｝～､￠''')
headpunct = ('''\t\n\x0b\x0c\r ([`{£¥‘“\u3000〈《「『【〔〖〝'''
             '''︵︷︹︻︽︿﹁﹃﹙﹛﹝（［｛￡￥''')
ucjk = frozenset(chain(
	range(0x1100, 0x11FF+1),
	range(0x2E80, 0xA4CF+1),
	range(0xA840, 0xA87F+1),
	range(0xAC00, 0xD7AF+1),
	range(0xF900, 0xFAFF+1),
	range(0xFE30, 0xFE4F+1),
	range(0xFF65, 0xFFDC+1),
	range(0xFF01, 0xFF0F+1),
	range(0xFF1A, 0xFF20+1),
	range(0xFF3B, 0xFF40+1),
	range(0xFF5B, 0xFF60+1),
	range(0x20000, 0x2FFFF+1)))

zhcmodel = None
zhmmodel = None
_curpath = os.path.normpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

RE_WS_IN_FW = re.compile(r'([\u2018\u2019\u201c\u201d\u2026\u2500\u2e80-\u312f\u3200-\u32ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\ufe30-\ufe57\uff00-\uffef])\s+(?=[\u2018\u2019\u201c\u201d\u2026\u2e80-\u312f\u3200-\u32ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\ufe30-\ufe57\uff00-\uffef])')

detokenize = lambda s: RE_WS_IN_FW.sub(r'\1', s).strip()

def splitsentence(sentence):
	# s = ''.join((chr(ord(ch)+0xFEE0) if ch in halfwidth else ch) for ch in sentence)
	s = sentence
	slist = []
	for i in resentencesp.split(s):
		if resentencesp.match(i) and slist:
			slist[-1] += i
		elif i:
			slist.append(i)
	return slist

def splithard(sentence, maxchar=None):
	slist = splitsentence(sentence)
	if maxchar is None:
		return slist
	slist1 = []
	for sent in slist:
		if len(sent) > maxchar:
			for i in resplitpunct.split(sent):
				if resplitpunct.match(i) and slist1:
					slist1[-1] += i
				elif i:
					slist1.append(i)
		else:
			slist1.append(sent)
	slist = slist1
	slist1 = []
	for sent in slist:
		if len(sent) > maxchar:
			slist1.extend(sent[i:i+maxchar] for i in range(0, len(sent), maxchar))
		else:
			slist1.append(sent)
	slist = slist1
	return slist

def fixmissing(slist):
	newlist = []
	for i in slist:
		newlist.extend(filter(None, refixmissing.split(i)))
	return newlist

def filterlist(slist):
	for i in slist:
		s = i.lstrip(tailpunct).rstrip(headpunct)
		if len(s) > 1:
			yield s

def addwalls(tokiter):
	lastwall = False
	for tok in tokiter:
		if tok in punct:
			if not lastwall and tok != '》':
				yield '<wall />'
			yield tok
			if tok != '《':
				yield '<wall />'
			lastwall = True
		else:
			yield tok
			lastwall = False

def calctxtstat(s):
	global zhcmodel, zhmmodel
	if zhcmodel is None:
		import json
		zhcmodel = json.load(open(os.path.join(_curpath, 'modelzhc.json'), 'r', encoding='utf-8'))
		zhmmodel = json.load(open(os.path.join(_curpath, 'modelzhm.json'), 'r', encoding='utf-8'))
	cscore = 0
	mscore = 0
	for ch in s:
		ordch = ord(ch)
		if 0x4E00 <= ordch < 0x9FCD:
			cscore += zhcmodel[ordch-0x4E00]
			mscore += zhmmodel[ordch-0x4E00]
	return (cscore, mscore)

def checktxttype(cscore, mscore):
	if cscore > mscore:
		return 'c'
	elif cscore < mscore:
		return 'm'
	else:
		return None

stripquotes = lambda s: s.lstrip('"‘“「『').rstrip('"’”」』')
fw2hw = lambda s: ''.join((chr(ord(ch)-0xFEE0) if ord(ch) in fullwidth else ch) for ch in s)
hw2fw = lambda s: ''.join((chr(ord(ch)+0xFEE0) if ch in halfwidth else ch) for ch in s)

def _test_fixsplit():
	test = """从高祖父到曾孙称为“九族”。这“九族”代表着长幼尊卑秩序和家族血统的承续关系。
《诗》、《书》、《易》、《礼》、《春秋》，再加上《乐》称“六经”，这是中国古代儒家的重要经典，应当仔细阅读。
这就是：宇宙间万事万物循环变化的道理的书籍。
《连山》、《归藏》、《周易》，是我国古代的三部书，这三部书合称“三易”，“三易”是用“卦”的形式来说明宇宙间万事万物循环变化的道理的书籍。
登楼而望，慨然而叹曰：“容容其山，旅旅其石，与地终也!吁嗟人乎!病之蚀气也，如水浸火。
吾闻老聃多寿，尝读其书曰：‘吾惟无身，是以无患。’盖欲窃之而未能也”齐宣王见孟子于雪宫。
“昔者齐景公问于晏子曰：‘吾欲观于转附、朝舞，遵海而南，放于琅邪。吾何修而可以比于先王观也？’
高祖说：“该怎样对付呢？”陈平说：“古代天子有巡察天下，召集诸侯。南方有云梦这个地方，陛下只管假装外出巡游云梦，在陈地召集诸侯。陈地在楚国的西边边境上，韩信听说天子因为爱好外出巡游，看形势必然没有什么大事，就会到国境外来拜见陛下。拜见，陛下趁机抓住他，这只是一个力士的事情而已。”“不知道。”高祖认为有道理。
。他们就是这样的。
""".strip().split('\n')
	for s in test:
		print(fixmissing(splitsentence(s)))

if __name__ == '__main__':
	import sys
	_test_fixsplit()
	#print(checktxttype(sys.stdin.read()))

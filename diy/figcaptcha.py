#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random
import collections
from pyfiglet import Figlet

pixels = (
    '@MBWQNg8&R$#D%Hm0qOpbd9A6GEKUwXPhSZ5ak4e32VyFoCnux'
    'IfsYjT[]Jz1t{v}Llc7i?)(r|=*+></\!"^;~_:,\'-.` '
)
charcount = len(pixels)

alphanum = 'ABCDEFGHJKLMNPRSTUVWXYZabcdefghjkmnoprstuvwxyz'

default_fonts = (
    'banner',
    'banner3',
    'basic',
)

class TextBlock:
    def __init__(self, captcha=''):
        self.lines = []
        # strip first blank lines
        begin = 0
        for l in captcha.rstrip().splitlines():
            if begin or l.strip():
                begin = 1
                self.lines.append(l)
        if not self.lines:
            self.lines.append('')
        self.width = max(map(len, self.lines))
        self.height = len(self.lines)
        self.lines = collections.deque(l.ljust(self.width) for l in self.lines)

    def hcat(self, other, justify=0):
        delta = other.height - self.height
        start = 0
        if delta > 0:
            if justify > 0:
                self.lines.extendleft(' '*self.width for i in range(delta))
            elif justify < 0:
                self.lines.extend(' '*self.width for i in range(delta))
            else:
                top = delta // 2
                self.lines.extendleft(' '*self.width for i in range(top))
                self.lines.extend(' '*self.width for i in range(delta - top))
            self.height = other.height
        elif delta < 0:
            if justify > 0:
                start = -delta
            elif justify == 0:
                start = -delta // 2
        for ln in range(start):
            self.lines[ln] += ' '*other.width
        for ln in range(other.height):
            self.lines[ln + start] += other.lines[ln]
        for ln in range(start + other.height, self.height):
            self.lines[ln] += ' '*other.width
        self.width += other.width

    def __str__(self):
        return '\n'.join(self.lines)


def getcaptcha(length, fontlist=default_fonts):
    f = Figlet(font=random.choice(fontlist))
    ans = ''.join(random.choice(alphanum) for i in range(length))
    ask = f.renderText(ans).rstrip()
    return (ask, ans)


def combinecaptcha(captchas):
    captchas = list(captchas)
    ans = ''.join(a for q, a in captchas)
    ask = TextBlock()
    for q, a in captchas:
        ask.hcat(TextBlock(q))
    return (str(ask).rstrip(), ans)


def noise(s, noise=.1, noisestrength=5):
    s = list(s)
    if noise < 1:
        noise = len(s) * noise
    noise = int(noise)
    textarea = [k for k, i in enumerate(s) if i != '\n']
    for i in range(noise):
        pix = random.choice(textarea)
        pixid = pixels.index(s[pix])
        s[pix] = pixels[random.randrange(
            max(pixid - noisestrength, 0), min(pixid + noisestrength, charcount))]
    return ''.join(s)


if __name__ == '__main__':
    ask, ans = combinecaptcha(getcaptcha(2) for i in range(2))
    print(noise(ask))
    print(ans)

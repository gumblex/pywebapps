#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import operator
import collections

UNK_STR = 255

re_proba1 = re.compile(r'^(\d+)=proba1\[(\d+)\]')
re_proba2 = re.compile(r'^(\d+)=proba2\[(\d+)\*256\+(\d+)\]')

class MarkovModel:
    def __init__(self, filename):
        self.proba1 = bytearray([UNK_STR] * 256)
        self.proba2 = bytearray([UNK_STR] * (256 * 256))
        self.first = bytearray([255] * 256)
        self.charsorted = bytearray(256 * 256)
        self.nbparts = collections.defaultdict(int)
        self.max_lvl = None
        self.max_len = None

        for i in range(256):
            for j in range(256):
                self.charsorted[i * 256 + j] = j

        with open(filename, 'r', encoding='ascii') as f:
            for ln in f:
                try:
                    match = re_proba1.match(ln)
                    if match:
                        i = int(match.group(1))
                        j = int(match.group(2))
                        if i == 0 or j > 255:
                            raise ValueError
                        self.proba1[j] = i
                        continue
                    match = re_proba2.match(ln)
                    if match:
                        i = int(match.group(1))
                        j = int(match.group(2))
                        k = int(match.group(3))
                        if i == 0 or j > 255 or k > 255:
                            raise ValueError
                        if (self.first[j] > k) and (i < UNK_STR):
                            self.first[j] = k
                        self.proba2[j * 256 + k] = i
                    else:
                        raise ValueError
                except ValueError:
                    raise ValueError(
                        '%s is not a valid Markov stats file. Invalid line: %s' %
                        (filename, ln))

        mcharsorted = memoryview(self.charsorted)
        mproba2 = memoryview(self.proba2)
        self.stupidsort(mcharsorted, self.proba1, 256)
        for i in range(1, 256):
            self.stupidsort(mcharsorted[i * 256:], mproba2[i * 256:], 256)

    def stupidsort(self, result, source, size):
        for i, res in enumerate(
            sorted(enumerate(source[:size]), key=operator.itemgetter(1))):
            result[i] = res[0]

    #nbparts =
        #mem_alloc(256 * (mkv_level + 1) * sizeof(long long) * (mkv_maxlen + 1))

    def nb_parts(self, lettre, length, level, max_lvl, max_len):
        out = 1;

        if level > max_lvl:
            return 0

        if length == max_len:
            self.nbparts[(level, length, lettre)] = 1
            return 1

        if self.nbparts[(level, length, lettre)]:
            return self.nbparts[(level, length, lettre)]

        for i in range(1, 256):
            if length:
                out += self.nb_parts(i, length + 1,
                    level + self.proba2[lettre * 256 + i], max_lvl, max_len)
            else:
                out += self.nb_parts(i, length + 1,
                    self.proba1[i], max_lvl, max_len)

        self.nbparts[(level, length, lettre)] = out
        return out

    def init(self, max_lvl, max_len, nbparts=None):
        self.max_lvl = max_lvl
        self.max_len = max_len
        if nbparts:
            self.nbparts = collections.defaultdict(int, nbparts)
            return nbparts[(0, 0, 0)]
        else:
            self.nbparts = collections.defaultdict(int)
            return self.nb_parts(0, 0, 0, max_lvl, max_len)

    def print_pwd(self, index):
        length = 1
        level = 0
        lvl = 0
        oldc = 0
        password = bytearray()

        if index > self.nbparts[(0, 0, 0)]:
            return

        length = 1;
        while index and (length <= self.max_len):
            for i in range(256):
                if length == 1:
                    level = self.proba1[self.charsorted[256 * 0 + i]]
                else:
                    level = lvl + self.proba2[oldc * 256 + self.charsorted[oldc * 256 + i]]
                if level > self.max_lvl:
                    i = 256
                    break
                if self.nbparts[(level, length, self.charsorted[oldc * 256 + i])] == 0:
                    break
                if (index <= self.nbparts[(level, length, self.charsorted[oldc * 256 + i])]):
                    break
                index -= self.nbparts[(level, length, self.charsorted[oldc * 256 + i])]
            if i == 256:
                break
            lvl = level
            password.append(self.charsorted[oldc * 256 + i])
            oldc = self.charsorted[oldc * 256 + i]
            length += 1

        return password.decode('utf-8'), index, lvl, length - 1


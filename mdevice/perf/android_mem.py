# encoding:utf-8
import os
import re
import sys

BaseDir = os.path.dirname(__file__)
sys.path.append(os.path.join(BaseDir, '..'))


class MemInfoPackage(object):
    RE_PROCESS = re.compile(r'\*\* MEMINFO in pid (\d+) \[(\S+)] \*\*')
    RE_TOTAL_PSS = re.compile(r'TOTAL\s+(\d+)')
    RE_JAVA_HEAP = re.compile(r"Java Heap:\s+(\d+)")
    RE_Native_HEAP = re.compile(r"Native Heap:\s+(\d+)")
    RE_System = re.compile(r"System:\s+(\d+)")

    pid = 0
    processName = ''
    datetime = ''
    totalPSS = 0
    totalAllocHeap = 0
    javaHeap = 0
    nativeHeap = 0
    system = 0

    def __init__(self, dump):
        self.dump = dump
        self._parse()

    def _parse(self):
        '''
        dumpsys meminfo package 中解析出需要的数据，由于版本变迁，这个数据的结构变化较多，
        比较了不同版本发现这两列数据total pss和Heap Alloc是都有的，而且这两个指标对于展示
        应用性能指标还是比较有代表性的。
        :return:
        '''
        match = self.RE_PROCESS.search(self.dump)
        if match:
            self.pid = match.group(1)
            self.processName = match.group(2)
        match = self.RE_TOTAL_PSS.search(self.dump)
        if match:
            self.totalPSS = round(float(match.group(1)) / 1024, 2)

        match = self.RE_JAVA_HEAP.search(self.dump)
        if match:
            self.javaHeap = round(float(match.group(1)) / 1024, 2)

        match = self.RE_Native_HEAP.search(self.dump)
        if match:
            self.nativeHeap = round(float(match.group(1)) / 1024, 2)

        match = self.RE_System.search(self.dump)
        if match:
            self.system = round(float(match.group(1)) / 1024, 2)

        result = self.dump.split('\n')  # 需要将其转为列表

        for line in result:
            if "TOTAL" in line and ":" not in line:
                tmp = line.split()
                self.totalAllocHeap = round(float(tmp[-2]) / 1024, 2)

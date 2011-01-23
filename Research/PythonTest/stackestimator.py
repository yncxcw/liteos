#!/usr/bin/python

# Copyright (c) 2006, Cleveland State University
# All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of Cleveland State University nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS ``AS IS''
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDERS AND CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE # OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.

# ---------------
# Summary: This file includes the implementation of stack-estimator.
# ---------------

# Author: William P. McCartney
# Last modified: Nov 17, 2006

import os
import re
import string
import sys

HEADER = 0
FUNCTION = 1

tinyos = {}
atomic_start = '__nesc_atomic_start'
atomic_end = '__nesc_atomic_end'

exception_names = ["__ctors_end-0x3a","ccitt_crc16_tabl","thread_task"]

RSTATE_TRASH = 0
RSTATE_SP_H = 1
RSTATE_SP_L = 2
RSTATE_CONST = 3
RSTATE_STATUS = 4

PSTATE_NONE  = 0
PSTATE_START = 1
PSTATE_STOP  = 2
PSTATE_INSANE = 3

class stack_parser:
    def parse_assembler_line(self, line):
        """ This function returns a dictionary of the parse line:
        1. 'opcode' - This is a string containing the opcode of the instruction i.e. 'ret'
        2. 'args' - These are the arguments of the instruction (possibly empty)
        3. 'comment' - This is the comment from objdump
        4.  'disassembly' - The disassembly from objdump
        5.  'address' - The address the instruction starts on
        6.  'size' - This is the size of the function in bytes
        This routine assumes that is_assembler_line has already validated the line..."""
        retval = {'args':'', 'comment':'', 'opcode':''}
        #print 'Parsing Assembled "%s"'% line
        array = string.split(line, "\t")
        retval['address'] = string.atol(array[0].strip()[:-1], 16)
        retval['disassembly'] = array[1].strip()
        retval['size'] = len(array[1].strip().split(' '))/2
        if(len(array) > 2):
            retval['opcode'] = array[2].strip()
        if(len(array) > 3):
            retval['args'] = array[3].strip()
            retval['leftovers'] = array[3:]
        if(len(array) > 4):
            retval['comment'] = array[4].strip()
        #print 'parsed output = %s' % retval
        return retval

    def is_assembler_line(self, line):
        """This routine returns true if the string passed to it contains a valid line from objdump.
          This routine could add many more checks, but right now it only looks for the header."""
        if(line.find('\t') == -1):
          return False
        #explode based upon tabs
        array = string.split(line, "\t")
        #return if we are empty
        if(not len(array)):
          return False
        temp = array[0].strip()
        try:
          if(temp[-1] != ":"):
            return False
          #perform the hex conversion
          numb = string.atol(temp[:-1],16)
        except:
          return False
        return True

    def is_function(self, line):
        if(line.find(" ") == -1):
            #print 'is_function - no space'
            return False
        array = line.split(' ')
        if(len(array) != 2):
            #print 'is_function - invalide split'
            return False
        try:
            m = re.search('<.+>:', array[1])
            if(m == None):
                #print 'is_function - no name'
                return False
        except:
            #print 'is_function - regex exception'
            return False
        #print 'is_function - Yay'
        return True

    def function_parse(self, line_array):
        """This function returns a dictionary of the following values:
        1. 'name' - The name of the function
        2. 'address' - This is a tuple of address range i.e. (0,200)
        3. 'instructions' - This is an array of parse lines included in the function
        4. 'lines' - The number of lines used... (for parent parser)"""
        retval = {'address':[0,0], 'instructions':[]}
        size = 0
        lines = line_array
        head = lines[0].split(' ')
        retval['address'][0] = string.atol(head[0].strip(), 16)
        m = re.search('<.+>:', head[1])
        retval['name'] = head[1][m.start()+1:m.end()-2]
        #Now iterate through the instructions contained...
        for line in lines[1:]:
            #debug#print 'line = "%s"'%line
            if(self.is_assembler_line(line)):
                p = self.parse_assembler_line(line)
                size += p['size']
                retval['instructions'] += [p]
            elif(line.find('...') != -1):
                pass
            else:
                #If we didn't find an instruction, then end of function...
                if(len(line) == 0):
                    ##print 'Stopping loop!!!'
                    break
        retval['address'][1] = retval['address'][0] + size
        retval['lines'] = len(retval['instructions']) + 1
        retval['size'] = size
        #print '%s parsed using %d lines' % (
        return retval

    def parse_objdump_array(self, lines):
        functions = []
        i = 0
        while (i < len(lines)):
            if(self.is_function(lines[i])):
                #debug#print 'beginning function parse'
                f = self.function_parse(lines[i:])
                i += f['lines']
                functions += [f]
                #debug#print 'ending function parse'
            else:
                if(len(lines[i])):
                    print 'Unknown Line "%s"' % lines[i]
                i += 1
        return(functions)


    ###This begins the platform specific linking...
    def find_function_by_address(self, functions, address):
        for x in functions:
            #print '%s range %d-%d' % (x['name'], x['address'][0], x['address'][1])
            if(x['address'][0] <= address <= x['address'][1]):
                return x
        print 'Warning, address 0x%8X does not represent a function' % address
        return {}

    def populate_dependencies(self, functions):
        global atomic_start, atomic_end
        for f in functions:
            stack_usage = 0
            fptr = False
            fptr_stack = 0
            deps = []
            deps_ints = []
            #This operates in a tinyos specific way...
            interrupt_override = False
            stack_usage_max = 0
            stack_usage_max_interrupts = 0
            interrupts_state = 0 #zero means enabled
            call_flag = False
            self.NewFunction()
            for i in f['instructions']:
                #print 'stack_usage = %d' % stack_usage
                if(i['opcode'] == self.push):
                    stack_usage += self.push_cost
                elif(i['opcode'] == self.call or i['opcode'] == self.icall):
                    stack_usage += self.call_cost
                    call_flag = True
                    if(i['opcode'] != self.icall):
                        try:
                          child = self.resolve_call(functions, i['args'])
                        except:
                          child = {}
                    else:
                        child = {}
                    if(child.has_key('name') and i['opcode'] != self.icall):
                        if(child['name'] == atomic_start):
                            interrupts_state += 1
                        if(child['name'] == atomic_end):
                            interrupts_state -= 1
                        deps += [child['name']]
                        deps_ints += [not not interrupts_state]
                    else:
                        fptr_stack = stack_usage
                        fptr = True
                elif(i['opcode'] == self.dint):
                    if(not interrupts_state):
                        interrupts_state = 1
                        if(f['name'] != atomic_start):
                            print 'Scary.. Disabled Interrupts called directly in %s' % f['name']
                elif(i['opcode'] == self.eint):
                    #This should probably be marked as an override somehow...
                    interrupts_state = 0
                    if(f['name'] != atomic_end):
                        interrupt_override = True
                        print 'Scary.. Enable Interrupts called directly in %s' % f['name']
                elif(i['opcode'] == self.pop):
                    #print 'popping const = %s' % self.push_cost
                    stack_usage -= self.push_cost
                else:
                    [stack_usage_temp, insanity] = self.process_instruction(i)
                    stack_usage += stack_usage_temp
                    if(insanity == PSTATE_START):
                        #print 'inlined atomic_start found'
                        interrupts_state += 1
                    elif(insanity == PSTATE_STOP):
                        #print 'inlined atomic_stop found'
                        interrupts_state -= 1
                    elif(insanity == PSTATE_INSANE):
                        print 'Scary, something strange happened in simulation - this code doesn\'t the nesc conventions'
                if(stack_usage > stack_usage_max):
                    #If this is the largest stack, save it...
                    stack_usage_max = stack_usage
                if((not interrupts_state) and (stack_usage < stack_usage_max_interrupts)):
                    #if this is the largest stack with interrupts enabled... save it...
                    stack_usage_max_interrupts = stack_usage
                if(call_flag):
                    #If we just made a call, we can remove the cost from the stack now...
                    stack_usage -= self.call_cost
                    call_flag = False
            f['stack'] = stack_usage_max
            f['stack_interrupts'] = stack_usage_max
            f['deps'] = deps
            f['deps_interrupts'] = deps_ints
            f['fptr'] = fptr
            f['fptr_stack'] = fptr_stack
            f['interrupt_override'] = interrupt_override
            if(fptr):
            	print 'function %s executes a function pointer...' % f['name']
        return functions

    def GetFunctionByName(self, functions, name):
        for f in functions:
            if(f['name'] == name):
                return f
        print 'ERROR FINDING FUNCTION %s' % name

    def recursion_check(self, functions, Repair=False):
        for f in functions:
            #print 'Checking %s for recursion' % (f['name'])
            if(self.recursion_check_int(functions, f, Repair)):
                return(True)
        return(False)

    def recursion_check_int(self, functions, func, Repair=False, stack=[]):
        """This routine iterates through all the functions checking for direct AND
        indirect recursion.  If a flag is set, it will automatically remove the
        recursive dependency."""
        if(stack.__contains__(func['name'])):
            #print 'f = %s' % func
            print 'Recursion found in the following call stack: %s' % (stack + [func['name']])
            if(stack[-1] == func['name']):
                print "The function %s is directly recursive, stack analysis isn't going to work correctly"
            else:
                print 'This call stack is indirectly recursive.  If the recursive call sequence is impossible, then you can try removing the recursion from the call graph via a command line option.'
            return(True)
        else:
            RemoveList = []
            for d in func['deps']:
                if(self.recursion_check_int(functions, self.GetFunctionByName(functions, d), Repair, stack + [func['name']])):
                    if(Repair):
                        RemoveList += [d]
                    else:
                        return(True)
            for d in RemoveList:
                func['deps'].remove(d)
        return(False)

    def ProcessStackSize(self, functions):
        for f in functions:
            f['stackExt'] = self.CalculateStackSize(functions, f)[0]
        return functions

    def CalculateStackSize(self, functions, f):
        """Based upon the list of functions and a specific entry (f) this determines f's worst
        case stack utilization.  This routine returns a tuple of three values.
        [Maximum Stack Utilization, Maximum Stack Utilization with Interrupts enabled, Interrupt Override (bool)]
        The interrupt override is set if EVER the function overrides interrupts and manually turns them on!!!"""
        possibles = []
        possibles_dint = []
        override = f['interrupt_override']
        for idx in range(0,len(f['deps'])):
            #Calculate the dependencies stack size
            [MaxStack, MaxStackDint, Override] = self.CalculateStackSize(functions, self.GetFunctionByName(functions, f['deps'][idx]))
            if(Override):
                possibles += [MaxStack]
                possibles_dint += [MaxStack]
                override = True
            elif(f['deps_interrupts'][idx]):
                possibles += [MaxStack]
                #nothing needs to be added... interrupts are disabled when called
                #possibles_dint += [MaxStackDint]
            else:
                possibles += [MaxStack]
                possibles_dint += [MaxStackDint]

        #Now calculate the maximum size...
        MaxStack = f['stack']
        if(len(possibles)):
            MaxStack += max(possibles)
        MaxStackDint = f['stack']
        if(len(possibles_dint)):
            MaxStackDint += max(possibles_dint)
        return([MaxStack, MaxStackDint, override])


    def PrintAll(self, functions):
        for f in functions:
            self.print_function(functions, f)

    def print_function(self, functions, f, stack = 0):
        output = "\t"
        for i in range(0,stack):
            output += '\t'
        if(f['fptr']):
            output += '*'
        output += '%s(%d)' % (f['name'], f['stackExt'])
        print output
        for name in f['deps']:
            self.print_function(functions, self.GetFunctionByName(functions, name), stack + 1)

    def print_function_short(self, functions, f):
        output = "\t"
        if(f['fptr']):
            output += '*'
        output += '%s(%d)' % (f['name'], f['stackExt'])
        print output

    def FindDependencyCount(self, functions):
        for f in functions:
            count = 0
            for g in functions:
                if(f['name'] in g['deps']):
                    count += 1
            f['DepCount'] = count
        return functions

    def ListTasks(self, functions):
        retval = []
        for f in functions:
            if(not f['DepCount']):
                if(not f['name'] in retval):
                    retval += [f['name']]
        return retval

    def nop(self, a, b):
        pass

    def CalculateOverallInterrupts(self, InterruptsStackEnabled, InterruptsStackDisabled):
        """Essentially, iterate through all possible occurances of interupts to figure
        out the maximum possible stack usage."""
        if(len(InterruptsStackEnabled) == 1):
          return(0)
        #strip off any temporary values!
        InterruptsStackEnabled_t = InterruptsStackEnabled[1:]
        InterruptsStackDisabled_t = InterruptsStackDisabled[1:]
        #print 'InterruptsStackEnabled = %s' % InterruptsStackEnabled
        #print 'InterruptsStackDisabled = %s' % InterruptsStackDisabled
        return(self.CalculateOverallInterruptsInt(0, InterruptsStackEnabled_t, InterruptsStackDisabled_t))

    def CalculateOverallInterruptsInt(self, size, InterruptsStackEnabled, InterruptsStackDisabled):
        result = []
        ##print 'Interupts Disabled = %s' % InterruptsStackDisabled
        ##print ' size = %s' % size
        if(len(InterruptsStackDisabled) != 0):
            for entry in range(0,len(InterruptsStackEnabled)):
                NewEn = InterruptsStackEnabled[:]
                NewDis = InterruptsStackDisabled[:]
                tempSize = size + InterruptsStackEnabled[entry]
                del NewEn[entry]
                del NewDis[entry]
                result += [max([self.CalculateOverallInterruptsInt(tempSize, NewEn, NewDis), size + InterruptsStackDisabled[entry]])]
            #print 'returning %s' % (max(result))
            return(max(result))
        else:
            #print 'returning %s' % size
            return(size)
    def BuildHeader(self, functions, tasks, InterruptOverhead, ThreadingOverhead):
        #
        global exception_names
        header = {}
        for x in tasks:
            title = x
            #Here we remove the '$' and anything before it...
            if(x.rfind('$') != -1):
                title = x[x.rfind('$')+1:]
            f = self.GetFunctionByName(functions, x)
            temp = self.CalculateStackSize(functions, f)
            TaskStack = temp[0]
            TaskIntStack = temp[1]
            MaximumStackSize = max([TaskIntStack + InterruptOverhead, TaskStack])
            if(header.has_key(title)):
                MaximumStackSize = max([MaximumStackSize, header[title]])
            header[title] = MaximumStackSize + ThreadingOverhead
        #Now write the file...
        f = open('stack.h', 'w')
        for x in header:
            if((x not in exception_names) and ("." not in x)):
                f.write('#define  %s_STACKSIZE  %d\n' % (x, header[x]))
        f.close()

    def OverallStack(self, functions, silent = False, short_print = False):
        global glPlatform
        global glFilename
        if(silent):
            internal_print_function = self.nop
        else:
            if(short_print):
                internal_print_function = self.print_function_short
            else:
                internal_print_function = self.print_function
        ints = parser.Interrupts(functions)
        tasks = parser.ListTasks(functions)
        TaskStack = []
        #This adds a simple
        IntList = [0]
        IntListExt = [0]
        SigList = [0]
        TaskList = [0]
        TaskIntList = [0]
        Threads = []
        StackTotalInt = 0
        InterruptNestCount = 0
        main = self.GetFunctionByName(functions, self.main(functions))
        internal_print_function(functions, main)
        StackTotalMain = main['stackExt']
        StackMainIndirect = main['fptr_stack']
        if not silent:
            print '*** Interrupts ***'
        for x in ints:
            f = self.GetFunctionByName(functions, x)
            [Stack, temp, Interrupt] = self.CalculateStackSize(functions, f)
            if(Interrupt):
                #This can possibly be optimized by using dint inside of an interrupt...
                IntList += [Stack]
                IntListExt += [temp]
            else:
                SigList += [Stack]
            #Calculate for simple method (bad)
            StackTotalInt += f['stackExt']
            InterruptNestCount += 1
            if not silent:
                if(not Interrupt):
                    print 'Signal:'
                else:
                    print 'Interrupt:'
            internal_print_function(functions, f)
        #Now spin through the different tasks
        if not silent:
            print '*** Tasks/Threads *** - These are simply uncalled functions'
        for x in tasks:
            f = self.GetFunctionByName(functions, x)
            temp = self.CalculateStackSize(functions, f)
            TaskList += [temp[0]]
            TaskIntList += [temp[1]]
            TaskStack += [f['stackExt']]
            internal_print_function(functions, f)
        print 'Simple Stack Analysis'
        print 'Stack due to interrupts = %4d' % (StackTotalInt + (self.InterruptCost * InterruptNestCount))
        print 'Stack due to tasks =      %4d' % max(TaskStack)
        print 'Stack due to Main =       %4d' % StackTotalMain
        TotalStack = StackTotalInt + max(TaskStack) + StackTotalMain + (self.InterruptCost * InterruptNestCount)
        print '                  Total   %4d' % TotalStack
        print ''
        print 'Context Sensitive Interrupt Masking Analysis'
        print 'Stack due to Tasks                      = %4d' % max(TaskList)
        print 'Stack due to Main                       = %4d' % StackTotalMain
        if(main['fptr']):
          print 'Stack due to below Task Execution       = %4d' % StackMainIndirect
        print 'Stack due to Tasks (Interrupts Enabled) = %4d' % max(TaskIntList)
        print 'Stack due to Signals(maximum)           = %4d' % max(SigList)
        #print 'Stack due to Interrupts (summation)     = %4d' % sum(IntList)
        print 'Stack due to Interrupts (calculation)   = %4d' % self.CalculateOverallInterrupts(IntList, IntListExt)
        InterruptOverhead = self.CalculateOverallInterrupts(IntList, IntListExt) + max(SigList) + (self.InterruptCost*(len(IntList)))

        print 'stack due to interrupt costs            = %4d' % (self.InterruptCost*(len(IntList)))
        print 'Interrupt overhead on all stacks        = %4d' % InterruptOverhead
        #Maximum between Stack Size of main loop with interrupts disabled or
        # Maximum of the interrupt enabled main loop + maximum signal depth + sum of all interrupt depth + cost of interrupt * (number of interrupts + 1)
        #TotalStack = (StackTotalMain + max([max(TaskList), max(TaskIntList) + max(SigList) + sum(IntList) + (self.InterruptCost * len(IntList))]))
        TotalStack = StackMainIndirect + max([max(TaskList), max(TaskIntList) + InterruptOverhead])
        if(StackTotalMain > TotalStack):
            TotalStack = StackTotalMain + InterruptOverhead
        #TotalStack = max([max(TaskList), max(TaskIntList) + InterruptOverhead])
        print '                                  Total = %4d' % TotalStack
        #resultsf = open("/home/r0gu3/stack_results.txt","a")
        #resultsf.write("%s %s %d\n" % (glFilename,glPlatform,TotalStack))
        #resultsf.close()
        #This is based upon the requirements of TinyThreads.
        ThreadingOverhead = 2 * self.call_cost
        #Now lets build the header..
        self.BuildHeader(functions, tasks, InterruptOverhead, ThreadingOverhead)
        return TotalStack

    def go(self, scanned, flags):
      output = self.parse_objdump_array(scanned)
      #print 'step 2'
      output = self.populate_dependencies(output)
      #Check for recursion in the graph... currently we have to bail out!!!
      #'RecursionFix':False, 'PrintCallGraph':False, 'PrintVerbose':False
      if(self.recursion_check(output, flags['RecursionFix'])):
          print 'Error, recursion found... exitting'
          return
      output = self.ProcessStackSize(output)
      #print 'step 4'
      output = self.FindDependencyCount(output)
      #parser.PrintAll(output)
      print '***************************************************************************'
      self.OverallStack(output, not flags['PrintCallGraph'], not flags['PrintVerbose'])
      if(flags['PrintSize']):
        print '***************************************************************************'
        print '  Function Sizes'
        total = 0
        def cmp(x,y):
          key='name'
          if(x[key] > y[key]):
            return(1);
          elif(x[key] < y[key]):
            return(-1);
          elif(x['name'] > y['name']):
            return(1);
          elif(x['name'] < y['name']):
            return(-1);
          else:
            return(0);
        output.sort(cmp)
        for x in output:
          size = x['address'][1] - x['address'][0]
          print' %16s %4s' % (x['name'],size)
          total += size
        print 'total size = %d' % total

class msp430_platform(stack_parser):
    def __init__(self):
        self.push_cost = 2
        self.call_cost = 2
        self.call = 'call'
        self.push = 'push'
        self.jump = 'jmp'
        self.pop = 'pop'
        self.eint = 'eint'
        self.dint = 'dint'
        self.icall = 'aflyingaardvark' # No opcode should ever match this...
        self.InterruptCost = 4

    def NewFunction(self):
        pass

    def process_instruction(self, inst):
    	"""This routine returns a tuple of two values:
    		1. The stack size increase or decrease
    		1. Whether something insane was done (i.e. 'alloca')"""
    	retval = 0
        if(inst['opcode'] == 'sub'):
            if(inst['leftovers'][1].strip() == 'r1'):
                retval = string.atol(inst['leftovers'][0].strip()[1:-1])
        elif(inst['opcode'] == 'decd'):
            if(inst['leftovers'][0].strip() == 'r1'):
                retval = 2
        elif(inst['opcode'] == 'incd'):
            if(inst['leftovers'][0].strip() == 'r1'):
                retval = -2
        elif((inst['opcode'] == 'add') and (len(inst['leftovers']) > 1)):
            if(inst['leftovers'][1].strip() == 'r1'):
                retval = -string.atol(inst['leftovers'][0].strip()[1:-1])
        elif((inst['opcode'] == 'dec') and (len(inst['leftovers']) > 1)):
            if(inst['leftovers'][0].strip() == 'r1'):
                retval = 1
        elif(inst['opcode'] == 'inc'):
            if(inst['leftovers'][0].strip() == 'r1'):
                retval = -1
        return([retval, False])

    def resolve_call(self, functions, args):
        args = args.strip()
        if(args[0] != '#'):
            print 'Invalid address found in call... (%s)' % args
            return({})
        address = string.atol(args[1:])
        if(address < 0):
            address = 0x10000 + address
        return self.find_function_by_address(functions, address)

    def main(self, functions):
        """This routine returns the name of the main function for the msp430"""
        return 'main'

    def Interrupts(self, functions):
        """This routine returns a list of names of functions which are interrupt vectors"""
        retval = []
        f = self.GetFunctionByName(functions, 'InterruptVectors')
        VectorBytes = f['instructions'][0]['disassembly'].strip()[:48].strip().split(' ')
        VectorBytes += f['instructions'][1]['disassembly'].strip()[:48].strip().split(' ')
        #print VectorBytes
        for i in range(0, len(VectorBytes)):
            if(i & 1):
                f = self.find_function_by_address(functions, string.atol(VectorBytes[i], 16) * 256 + string.atol(VectorBytes[i - 1], 16))
                if(f.has_key('name')):
                    if(not f['name'] in retval):
                        retval += [f['name']]
        return retval

    def ListTasks(self, functions):
        """This routine wraps the general purpose..."""
        retval = stack_parser.ListTasks(self, functions)
        for x in self.Interrupts(functions) + ["InterruptVectors", "main", "_unexpected_", "__stop_progExec__"]:
            if(x in retval):
                retval.remove(x)
        return(retval)
    #def resolve_jump(self, functions, args):
    #    return find_function_by_address(functions,


class avr_platform(stack_parser):
    """This contains everything specific to the ATMega platforms."""
    def __init__(self):
        self.push_cost = 1
        self.call_cost = 2
        self.call = 'call'
        self.push = 'push'
        self.jump = 'jmp'
        self.pop = 'pop'
        self.eint = 'sei'
        #This has been removed, so that cli instructions are passed into the simulation
        #self.dint = 'cli'
        self.dint = 'does not exist'
        self.icall = 'icall'
        #This needs to be updated for the avr
        self.InterruptCost = 2

    def NewFunction(self):
        self.stack_top = []
        self.stack_bottom = []
        self.carry_bit = False #We are just initializing the carry bit
        self.reg = range(0,32)
        self.reg_state = range(0,32)
        self.atomic_start = False
        for i in range(0,32):
            self.reg[i] = 0
            self.reg_state[i] = RSTATE_TRASH

#RSTATE_TRASH = 0
#RSTATE_SP_H = 0
#RSTATE_SP_L = 0
#RSTATE_CONST = 0
    def process_instruction(self, inst):
        args = string.split(inst['args'], ',')
        for i in range(0,len(args)):
            args[i] = args[i].strip()
        if(inst['opcode'] == 'cli'):
            #essentially, this could (should) be an atomic_start which was inlined
            if(self.atomic_start):
                return([0,PSTATE_START])
                self.atomic_start = False
            else:
                return([0,PSTATE_INSANE])
        elif(inst['opcode'] == 'in'):
            if(args[1] == '0x3d'):
                #self.stack_top += [int(args[0][1:])]
                print 'Loading SP_L to %d' % int(args[0][1:])
                self.reg[int(args[0][1:])] = 0
                self.reg_state[int(args[0][1:])] = RSTATE_SP_L
            elif(args[1] == '0x3e'):
                print 'Loading SP_H to %d' % int(args[0][1:])
                #self.stack_bottom += [int(args[0][1:])]
                self.reg[int(args[0][1:])] = 0
                self.reg_state[int(args[0][1:])] = RSTATE_SP_H
            elif(args[1] == '0x3f'):
                #'Loading from status register'
                self.reg[int(args[0][1:])] = 0
                self.reg_state[int(args[0][1:])] = RSTATE_STATUS
                #print 'stored status into register %d' % int(args[0][1:])
                self.atomic_start = True
        elif(inst['opcode'] == 'out'):
            if(args[0] == '0x3d'):
                try:
                    reg = int(args[1][1:])
                    #idx = self.stack_top.index('r%d' % reg)
                    if(self.reg_state[reg] == RSTATE_SP_L):
                        if(self.reg[reg]):
                          print 'setting spl to %s' % (self.reg[reg])
                        #print 'setting sph to %s' % (self.reg[reg])
                        return([self.reg[reg], False])
                    else:
                        print 'Stack pointer being set to unknown state'
                except:
                    print 'args=%s' % args
                    print 'Failed to process %s' % inst
                    pass
            elif(args[0] == '0x3e'):
                try:
                    reg = int(args[1][1:])
                    if(self.reg_state[reg] == RSTATE_SP_H):
                        if(self.reg[reg]):
                          print 'setting sph to %s (* 256)' % (self.reg[reg])
                        return([self.reg[reg] * 256, False])
                    else:
                        print 'Stack pointer being set to unknown state'
                    #idx = self.stack_top.index('r%d' % reg)
                except:
                    print 'args=%s' % args
                    print 'Failed to process %s' % inst
                    pass
            elif(args[0] == '0x3f'):
                #'Storing to status register'
                try:
                    reg = int(args[1][1:])
                    #print 'restoring status from register %d' % reg
                    #print 'instruction = %s' % inst
                    if(self.reg_state[reg] == RSTATE_STATUS):
                        return([0, PSTATE_STOP])
                    else:
                        print 'Status register being set to unknown state'
                        #print 'instruction = %s' % inst
                except:
                    print 'args=%s' % args
                    print 'Failed to process %s' % inst
                    pass
        elif((inst['opcode'] == 'sbci') or (inst['opcode'] == 'subi')):
            reg = int(args[0][1:])
            const = int(args[1], 16)
            if(self.reg_state[reg] == RSTATE_SP_L) or (self.reg_state[reg] == RSTATE_SP_H):
                self.reg[reg] += const
                if(self.reg_state[reg] == RSTATE_SP_H):
                  self.reg[reg] = self.reg[reg] % 256
                if(const):
                  if(self.reg_state[reg] == RSTATE_SP_L):
                    print 'adding %d to the Lower SP reg' % const
                  else:
                    print 'adding %d to the Upper SP reg' % const
        elif(inst['opcode'] == 'mov'):
            dest = int(args[0][1:])
            src = int(args[1][1:])
            self.reg[dest] = self.reg[src]
            self.reg_state[dest] = self.reg_state[src]
            #reg = int(inst['leftovers'][0][1:-1])
            #print 'sbci => %s' % inst
            #return([0, False])
        #elif(inst['opcode'] == 'subi')

            #print 'subi => %s' % inst
        #    pass
        #~ if(inst['opcode'] == 'sub'):
            #~ if(inst['leftovers'][1].strip() == 'r1'):
                #~ return(string.atol(inst['leftovers'][0].strip()[1:-1]))
        #~ elif(inst['opcode'] == 'decd'):
            #~ if(inst['leftovers'][0].strip() == 'r1'):
                #~ return(2)
        #~ elif(inst['opcode'] == 'incd'):
            #~ if(inst['leftovers'][0].strip() == 'r1'):
                #~ return(-2)
        #~ elif((inst['opcode'] == 'add') and (len(inst['leftovers']) > 1)):
            #~ if(inst['leftovers'][1].strip() == 'r1'):
                #~ return(-string.atol(inst['leftovers'][0].strip()[1:-1]))
        #~ elif((inst['opcode'] == 'dec') and (len(inst['leftovers']) > 1)):
            #~ if(inst['leftovers'][0].strip() == 'r1'):
                #~ return(1)
        #~ elif(inst['opcode'] == 'inc'):
            #~ if(inst['leftovers'][0].strip() == 'r1'):
                #~ return(-1)
        return([0, False])

    def resolve_call(self, functions, args):
        args = args.strip()
        #if(args[0] != '#'):
        #    print 'Invalid address found in call... (%s)' % args
        #    return({})
        address = string.atol(args, 16)
        if(address < 0):
            #Fix the address range
            address = 0x10000 + address
        return self.find_function_by_address(functions, address)

    def main(self, functions):
        """This routine returns the name of the main function for the msp430"""
        return 'main'

    def Interrupts(self, functions):
        """This routine returns a list of names of functions which are interrupt vectors"""
        retval = []
        f = self.GetFunctionByName(functions, '__vectors')
        for i in f['instructions']:
            try:
              f = self.find_function_by_address(functions, string.atol(i['args'], 16))
              if(f.has_key('name')):
                if(not f['name'] in retval):
                    retval += [f['name']]
            except:
              pass
        return retval

    def ListTasks(self, functions):
        """This routine wraps the general purpose..."""
        retval = stack_parser.ListTasks(self, functions)
        for x in self.Interrupts(functions) + ["InterruptVectors", "main", "_unexpected_", "__stop_progExec__"]:
            if(x in retval):
                retval.remove(x)
        return(retval)



msp430_boards = ['telos', 'telosa', 'telosb', 'tmote', 'telosa', 'eyesIFX', 'eyesIFXv1', 'eyesIFXv2']
avr_boards = ['mica', 'mica2', 'micaz', 'atmega8', 'mica2dot', 'rene2', 'mica128']
def usage():
    #Usage
    print 'USAGE:'
    print '1. cd apps/Blink'
    print '2. Compile the application as desired, i.e. make mica2'
    print '3. Run StackEstimator:'
    print ''
    print 'stack_estimator [flags] [platform] [filename]'
    print '    i.e.     stack_estimator telosb'
    print ''
    print ' -r    Remove any recursions found.  Only use this if you know what you are doing.'
    print ' -p    Print the call graph.'
    print ' -v    Print the call graph in depth.'
    print ' -b    Specify the function to disable interrupts (i.e. begin_atomic)'
    print ' -e    Specify the function to restore interrupt state (i.e. end_atomic)'
    print ''
    print 'Valid Platforms: %s' % string.join((msp430_boards + avr_boards), ' ')
    print ''
    sys.exit(1)

def ProcessArguments(args):
    """Returns a tuple described below
    [platform, Filename, flags]
    Where flags is a dictionary of settings."""
    global atomic_start, atomic_end
    state = 0
    Platform = ""
    Filename = ""
    Flags = {'RecursionFix':False, 'PrintCallGraph':False, 'PrintVerbose':False, 'PrintSize':False}
    Next = 0
    for i in range(1, len(args)):
        if(Next == 1):
            atomic_start = args[i]
            print 'atomic_start set to %s' % atomic_start
            Next = 0
        elif(Next == 2):
            atomic_end = args[i]
            print 'atomic_end set to %s' % atomic_end
            Next = 0
        elif(args[i][0] == '-'):
            for flag in args[i].strip():
                if(flag == 'r'):
                    Flags['RecursionFix'] = True
                elif(flag == 'p'):
                    Flags['PrintCallGraph'] = True
                elif(flag == 'v'):
                    Flags['PrintVerbose'] = True
                elif(flag == 's'):
                    Flags['PrintSize'] = True
                elif(flag == 'b'):
                    Next = 1
                elif(flag == 'e'):
                    Next = 2
                elif(flag == '-'):
                    pass
                else:
                    print 'Unknown Flag(s): %s' % args[i]
                    return({})
        elif(state == 0):
            Platform = args[i]
            state += 1
        elif(state == 1):
            Filename = args[i]
            state += 1
        else:
            print 'Too Many arguments'
            return({})
    if(Platform == ""):
        print 'Too Many arguments'
        return({})
    if(Filename == ""):
        Filename = "./build/" + Platform + "/main.exe"
    return([Platform, Filename, Flags])

    #
if __name__ == "__main__":
    global glPlatform
    global glFilename
    args = ProcessArguments(sys.argv)
    if(len(args) < 3):
        usage()
    [Platform, ElfFilename, Flags] = args
    glPlatform = Platform
    glFilename = os.getenv("APPNAME")
    dump = ""
    for p in msp430_boards:
        if(p == Platform):
            dump = 'msp430-objdump'
            parser = msp430_platform()
    for p in avr_boards:
        if(p == Platform):
            dump = 'avr-objdump'
            parser = avr_platform()
    if dump == "":
        usage()
    #build the objdump command string...
    command = string.join([dump, "-d", ElfFilename], ' ')
    #Run the command... and read the output
    pipe = os.popen(command)
    output = pipe.read()
    pipe.close()
    #Make an array from the output
    scanned = string.split(output, "\n")
    #Process the data...
    parser.go(scanned, Flags)
    #Goodnight :)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单帧传送格式码字生成工具 (CAN 2.0B Extended Frame Generator)
支持命令行使用

协议格式：
- Byte0: ID[28:27] + ID[26:21]
- Byte1: ID[20:19] + ID[18] + SRR + IDE + ID[17:15]
- Byte2: ID[14:13] + ID[12:11] + ID[10:7]
- Byte3: ID[6:5] + ID[4:0] + RTR
- Byte4: 00B + r1 + r0 + DLC

用法:
  命令行: python can_frame_tool.py [选项]

示例:
  python can_frame_tool.py --priority 0 --src 0x00 --multicast 0 --dst 0x28 --seq 0 --func 0 --dlc 1
  python can_frame_tool.py -p 0 -s 0 -m 0 -d 40 -f 0 -c 0 -l 1
  python can_frame_tool.py -i
"""

import argparse
import sys
import os

__version__ = "1.0.0"


def calculate_byte1(m, d):
    """计算Byte1: ID[20:19] + ID[18] + SRR + IDE + ID[17:15]"""
    return ((m & 0x3) << 6) | ((d & 0x20) << 0) | (0b1 << 4) | (0b1 << 3) | ((d >> 2) & 0x7)


def calculate_byte2(d, f):
    """计算Byte2: ID[14:13] + ID[12:11] + ID[10:7]"""
    return ((d & 0x3) << 6) | (0b11 << 4) | ((f >> 2) & 0xF)


def calculate_byte3(f, fc):
    """计算Byte3: ID[6:5] + ID[4:0] + RTR"""
    return ((f & 0x3) << 6) | ((fc & 0x1F) << 1) | 0b0


def calculate_byte4(dlc):
    """计算Byte4: 00B + r1 + r0 + DLC"""
    return (0b00 << 6) | (0 << 5) | (0 << 4) | (dlc & 0x0F)


def generate_frame(p, s, m, d, seq_flag, f, fc, dlc, data_bytes):
    """
    生成CAN扩展帧码字
    
    参数:
        p: 优先级 ID[28:27] (0-3)
        s: 源节点地址 ID[26:21] (0-63)
        m: 组播标识 ID[20:19] (0-3)
        d: 目的节点地址 ID[18:13] (0-63)
        seq_flag: 帧序号标志 ID[12:11] (0-3)
        f: 帧序号 ID[10:5] (0-63)
        fc: 功能码 ID[4:0] (0-31)
        dlc: 数据长度 (1-8)
        data_bytes: 数据字节列表
    
    返回:
        (id29, frame, sum_val)
    """
    # 构建29位ID
    # ID[28:27]=优先级, ID[26:21]=源地址, ID[20:19]=组播, ID[18:13]=目的地址
    # ID[12:11]=帧序号标志, ID[10:5]=帧序号, ID[4:0]=功能码
    id29 = (p << 27) | (s << 21) | (m << 19) | (d << 13) | (seq_flag << 11) | (f << 5) | fc
    
    # Byte0: ID[28:27] + ID[26:21]
    byte0 = (id29 >> 21) & 0xFF
    
    # Byte1-Byte4
    byte1 = calculate_byte1(m, d)
    byte2 = calculate_byte2(d, f)
    byte3 = calculate_byte3(f, fc)
    byte4 = calculate_byte4(dlc)
    
    # 构建帧
    frame = [byte0, byte1, byte2, byte3, byte4]
    
    # 添加数据字节
    user_data_count = max(0, dlc - 1)
    for i in range(user_data_count):
        if i < len(data_bytes):
            frame.append(data_bytes[i] & 0xFF)
        else:
            frame.append(0)
    
    # 计算SUM
    sum_val = sum(frame[5:5+user_data_count]) & 0xFF
    frame.append(sum_val)
    
    return id29, frame, sum_val


def format_output(id29, frame, sum_val, verbose=True):
    """格式化输出"""
    id_hex = f"{id29:08X}"
    frame_hex = ' '.join(f"{b:02X}" for b in frame)
    
    output = []
    output.append(f"29位扩展标识符 (ID): 0x{id_hex}")
    output.append(f"完整帧十六进制码字: {frame_hex}")
    
    if verbose:
        output.append("")
        output.append("字节明细:")
        output.append(f"  Byte0: {frame[0]:02X} ({frame[0]:08b}) - ID[28:27]+ID[26:21] (优先级+源节点)")
        output.append(f"  Byte1: {frame[1]:02X} ({frame[1]:08b}) - ID[20:19]+ID[18]+SRR+IDE+ID[17:15]")
        output.append(f"  Byte2: {frame[2]:02X} ({frame[2]:08b}) - ID[14:13]+ID[12:11]+ID[10:7]")
        output.append(f"  Byte3: {frame[3]:02X} ({frame[3]:08b}) - ID[6:5]+ID[4:0]+RTR")
        output.append(f"  Byte4: {frame[4]:02X} ({frame[4]:08b}) - 00+r1+r0+DLC")
        
        user_data_count = len(frame) - 6
        for i, b in enumerate(frame[5:-1]):
            if i < user_data_count:
                output.append(f"  Byte{5+i}: {b:02X} ({b:08b}) - 数据 Byte{i}")
            else:
                output.append(f"  Byte{5+i}: {b:02X} ({b:08b}) - SUM")
        output.append(f"  SUM:   {sum_val:02X} ({sum_val:08b})")
        
        output.append("")
        output.append("位域分解:")
        output.append(f"  优先级 ID[28:27]: {(id29 >> 27) & 0x3:02b}")
        output.append(f"  源节点地址 ID[26:21]: {(id29 >> 21) & 0x3F:06b} (0x{(id29 >> 21) & 0x3F:02X})")
        output.append(f"  组播标识 ID[20:19]: {(id29 >> 19) & 0x3:02b}")
        output.append(f"  目的节点地址 ID[18:13]: {(id29 >> 13) & 0x3F:06b} (0x{(id29 >> 13) & 0x3F:02X})")
        output.append(f"  帧序号标志 ID[12:11]: {(id29 >> 11) & 0x3:02b}")
        output.append(f"  帧序号 ID[10:5]: {(id29 >> 5) & 0x3F:06b} (0x{(id29 >> 5) & 0x3F:02X})")
        output.append(f"  功能码 ID[4:0]: {id29 & 0x1F:05b} (0x{id29 & 0x1F:02X})")
    
    return '\n'.join(output)


def parse_num(s, max_val, mode='hex'):
    """解析数字"""
    s = s.strip()
    if not s:
        return None
    
    base = 10
    if mode == 'hex':
        if s.endswith('h') or s.endswith('H'):
            s = s[:-1]
        base = 16
    elif mode == 'bin':
        if s.endswith('b') or s.endswith('B'):
            s = s[:-1]
        base = 2
    
    try:
        val = int(s, base)
        if 0 <= val <= max_val:
            return val
    except ValueError:
        pass
    return None


def run_cli():
    """命令行模式"""
    parser = argparse.ArgumentParser(
        description='CAN 2.0B扩展帧码字生成工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python can_frame_tool.py --priority 0 --src 0x00 --multicast 0 --dst 0x28 --seq 0 --func 0 --dlc 1
  python can_frame_tool.py -p 0 -s 0 -m 0 -d 40 -f 0 -c 0 -l 1 -D 1A,2B,00
  python can_frame_tool.py -i
'''
    )
    
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    parser.add_argument('-p', '--priority', type=str, default='0', help='优先级 ID[28:27] (0-3, 默认: 0)')
    parser.add_argument('-s', '--src', '--src-addr', type=str, default='0', help='源节点地址 ID[26:21] (0-63, 默认: 0)')
    parser.add_argument('-m', '--multicast', type=str, default='0', help='组播标识 ID[20:19] (0-3, 默认: 0)')
    parser.add_argument('-d', '--dst', '--dst-addr', type=str, default='0', help='目的节点地址 ID[18:13] (0-63, 默认: 0)')
    parser.add_argument('--seq-flag', type=str, default='3', help='帧序号标志 ID[12:11] (0-3, 默认: 3=11b)')
    parser.add_argument('-f', '--seq', '--frame-seq', type=str, default='0', help='帧序号 ID[10:5] (0-63, 默认: 0)')
    parser.add_argument('-c', '--func', '--func-code', type=str, default='0', help='功能码 ID[4:0] (0-31, 默认: 0)')
    parser.add_argument('-l', '--dlc', type=int, default=1, choices=range(1, 9), help='数据长度 DLC (1-8, 默认: 1)')
    parser.add_argument('-D', '--data', type=str, help='数据字节 (逗号分隔, 十六进制, 不含SUM)')
    parser.add_argument('--mode', choices=['hex', 'dec', 'bin'], default='hex', help='输入数字的进制 (默认: hex)')
    parser.add_argument('-i', '--interactive', action='store_true', help='交互式输入')
    parser.add_argument('-o', '--output', type=str, help='输出文件路径')
    parser.add_argument('-q', '--quiet', action='store_true', help='简洁输出 (只显示码字)')
    
    args = parser.parse_args()
    mode = args.mode
    
    if args.interactive:
        print("\n=== CAN 2.0B 扩展帧码字生成器 (交互模式) ===\n")
        print("按回车使用默认值\n")
        
        def input_val(prompt, max_val, default):
            while True:
                val = input(f"{prompt} [{default}]: ").strip()
                if not val:
                    return default
                result = parse_num(val, max_val, 'hex')
                if result is not None:
                    return result
                print(f"  无效输入，请输入 0-{max_val} 范围内的值 (十六进制)")
        
        p = input_val("优先级 ID[28:27] (0-3)", 3, 0)
        s = input_val("源节点地址 ID[26:21] (0-3F)", 63, 0)
        m = input_val("组播标识 ID[20:19] (0-3)", 3, 0)
        d = input_val("目的节点地址 ID[18:13] (0-3F)", 63, 0)
        seq_flag = input_val("帧序号标志 ID[12:11] (0-3, 默认11b)", 3, 3)
        f = input_val("帧序号 ID[10:5] (0-3F)", 63, 0)
        fc = input_val("功能码 ID[4:0] (0-1F)", 31, 0)
        
        dlc_str = input(f"数据长度 DLC (1-8) [1]: ").strip()
        dlc = int(dlc_str) if dlc_str else 1
        dlc = max(1, min(8, dlc))
        
        data_str = input("数据字节 (逗号分隔, 十六进制, 如: 1A,2B,00) []: ").strip()
        data_bytes = []
        if data_str:
            for b in data_str.split(','):
                b = b.strip()
                if b:
                    try:
                        if b.endswith('h') or b.endswith('H'):
                            data_bytes.append(int(b[:-1], 16))
                        else:
                            data_bytes.append(int(b, 16))
                    except ValueError:
                        pass
    else:
        p = parse_num(args.priority, 3, mode)
        s = parse_num(args.src, 63, mode)
        m = parse_num(args.multicast, 3, mode)
        d = parse_num(args.dst, 63, mode)
        seq_flag = parse_num(args.seq_flag, 3, mode)
        f = parse_num(args.seq, 63, mode)
        fc = parse_num(args.func, 31, mode)
        dlc = args.dlc
        
        data_bytes = []
        if args.data:
            for b in args.data.split(','):
                b = b.strip()
                if b:
                    try:
                        if b.endswith('h') or b.endswith('H'):
                            data_bytes.append(int(b[:-1], 16))
                        else:
                            data_bytes.append(int(b, 16))
                    except ValueError:
                        pass
    
    if None in [p, s, m, d, seq_flag, f, fc]:
        print("错误: 无效的输入参数", file=sys.stderr)
        sys.exit(1)
    
    # 生成帧
    id29, frame, sum_val = generate_frame(p, s, m, d, seq_flag, f, fc, dlc, data_bytes)
    
    # 输出结果
    result_text = format_output(id29, frame, sum_val, verbose=not args.quiet)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result_text)
        print(f"结果已保存到: {args.output}")
    else:
        print(result_text)


def run_gui():
    """GUI模式 (需要tkinter)"""
    try:
        import tkinter as tk
        from tkinter import ttk, messagebox, scrolledtext
    except ImportError:
        print("错误: tkinter模块不可用，请使用命令行模式", file=sys.stderr)
        print("运行 'python can_frame_tool.py -i' 启动交互模式", file=sys.stderr)
        sys.exit(1)
    
    class CANFrameGenerator:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("单帧传送格式码字生成工具 v1.0")
            self.root.geometry("1000x820")
            self.root.resizable(True, True)
            
            self.colors = {
                'bg_dark': '#0d1117',
                'bg_card': '#161b22',
                'bg_input': '#21262d',
                'bg_input_focus': '#30363d',
                'border': '#30363d',
                'border_focus': '#58a6ff',
                'text_primary': '#f0f6fc',
                'text_secondary': '#8b949e',
                'text_muted': '#6e7681',
                'accent_blue': '#58a6ff',
                'accent_cyan': '#39d353',
                'accent_purple': '#a371f7',
                'accent_orange': '#d29922',
                'accent_red': '#f85149',
                'success': '#238636',
                'warning': '#9e6a03',
            }
            
            self.root.configure(bg=self.colors['bg_dark'])
            self.style = ttk.Style()
            self.style.theme_use('clam')
            self.configure_styles()
            self.create_widgets()
            
        def configure_styles(self):
            self.style.configure('Title.TLabel', background=self.colors['bg_dark'], 
                                foreground=self.colors['accent_blue'], 
                                font=('Microsoft YaHei', 18, 'bold'))
            self.style.configure('Card.TLabelframe', background=self.colors['bg_card'], 
                                foreground=self.colors['text_primary'],
                                borderwidth=0, relief='flat')
            self.style.configure('Card.TLabelframe.Label', background=self.colors['bg_card'], 
                                foreground=self.colors['accent_blue'],
                                font=('Microsoft YaHei', 11, 'bold'))
            
        def create_card(self, parent, title, row=0, column=0, rowspan=1, columnspan=1, sticky='nsew', padx=5, pady=5):
            card = tk.Frame(parent, bg=self.colors['bg_card'], relief='flat', bd=0,
                          highlightbackground=self.colors['border'], highlightthickness=1)
            card.grid(row=row, column=column, rowspan=rowspan, columnspan=columnspan, 
                     sticky=sticky, padx=padx, pady=pady)
            
            if title:
                header = tk.Frame(card, bg=self.colors['bg_card'])
                header.pack(fill='x', padx=12, pady=(12, 8))
                
                indicator = tk.Frame(header, bg=self.colors['accent_blue'], width=4, height=20)
                indicator.pack(side='left', padx=(0, 8))
                
                tk.Label(header, text=title, bg=self.colors['bg_card'], 
                        fg=self.colors['accent_blue'],
                        font=('Microsoft YaHei', 11, 'bold')).pack(side='left')
            
            content = tk.Frame(card, bg=self.colors['bg_card'])
            if title:
                content.pack(fill='both', expand=True, padx=12, pady=(0, 12))
            else:
                content.pack(fill='both', expand=True, padx=12, pady=12)
            
            return card, content
        
        def create_input_field(self, parent, label, bits_hint, row, width=10, bit_width=0):
            field_frame = tk.Frame(parent, bg=self.colors['bg_card'])
            field_frame.pack(fill='x', pady=4)
            
            label_row = tk.Frame(field_frame, bg=self.colors['bg_card'])
            label_row.pack(fill='x')
            
            tk.Label(label_row, text=label, bg=self.colors['bg_card'], 
                    fg=self.colors['text_primary'],
                    font=('Microsoft YaHei', 10)).pack(side='left')
            
            tk.Label(label_row, text=bits_hint, bg=self.colors['bg_card'], 
                    fg=self.colors['text_muted'],
                    font=('Consolas', 8)).pack(side='right')
            
            input_frame = tk.Frame(field_frame, bg=self.colors['bg_input'], 
                                   highlightbackground=self.colors['border'],
                                   highlightthickness=1)
            input_frame.pack(fill='x', pady=(4, 0))
            
            entry = tk.Entry(input_frame, width=width, bg=self.colors['bg_input'], 
                            fg=self.colors['accent_blue'],
                            font=('Consolas', 13, 'bold'), justify='center',
                            insertbackground=self.colors['accent_blue'],
                            relief='flat', bd=0)
            entry.pack(fill='x', padx=8, pady=8)
            
            entry.bind('<FocusIn>', lambda e: self.on_entry_focus(entry, True))
            entry.bind('<FocusOut>', lambda e: self.on_entry_focus(entry, False))
            entry.bind('<KeyRelease>', lambda e: self.update_binary_display())
            
            if bit_width > 0:
                bin_frame = tk.Frame(field_frame, bg=self.colors['bg_input'],
                                    highlightbackground=self.colors['accent_orange'],
                                    highlightthickness=1)
                bin_frame.pack(fill='x', pady=(4, 0))
                
                bin_label = tk.Label(bin_frame, text="二进制: -", bg=self.colors['bg_input'],
                                    fg=self.colors['accent_orange'],
                                    font=('Consolas', 11), padx=8, pady=4)
                bin_label.pack(anchor='w')
                
                return entry, bin_label, bit_width
            
            return entry
        
        def update_binary_display(self, trigger_generate=True):
            for name, info in self.entries.items():
                if 'bin_label' in info and 'bit_width' in info:
                    try:
                        val = int(info['entry'].get(), 16)
                        bin_str = bin(val)[2:].zfill(info['bit_width'])
                        info['bin_label'].config(text=f"二进制: {bin_str}")
                    except ValueError:
                        info['bin_label'].config(text="二进制: -")
            if trigger_generate and hasattr(self, 'id_output'):
                self.generate_frame()
        
        def on_entry_focus(self, entry, focused):
            if focused:
                entry.master.configure(highlightbackground=self.colors['border_focus'],
                                      highlightthickness=2)
            else:
                entry.master.configure(highlightbackground=self.colors['border'],
                                      highlightthickness=1)
        
        def create_fixed_field(self, parent, label, value, color_key='accent_orange'):
            field_frame = tk.Frame(parent, bg=self.colors['bg_card'])
            field_frame.pack(fill='x', pady=4)
            
            tk.Label(field_frame, text=label, bg=self.colors['bg_card'], 
                    fg=self.colors[color_key],
                    font=('Microsoft YaHei', 9)).pack(side='left')
            
            value_frame = tk.Frame(field_frame, bg=self.colors['bg_input'],
                                  highlightbackground=self.colors['accent_orange'],
                                  highlightthickness=1)
            value_frame.pack(side='right')
            
            tk.Label(value_frame, text=value, bg=self.colors['bg_input'], 
                    fg=self.colors[color_key],
                    font=('Consolas', 11), padx=8, pady=4).pack()
        
        def create_widgets(self):
            main_frame = tk.Frame(self.root, bg=self.colors['bg_dark'])
            main_frame.pack(fill='both', expand=True, padx=15, pady=15)
            
            for i in range(3):
                main_frame.columnconfigure(i, weight=1)
            main_frame.rowconfigure(2, weight=1)
            
            title_frame = tk.Frame(main_frame, bg=self.colors['bg_dark'])
            title_frame.grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 15))
            
            title_container = tk.Frame(title_frame, bg=self.colors['bg_dark'])
            title_container.pack()
            
            tk.Label(title_container, text="◈", bg=self.colors['bg_dark'], 
                    fg=self.colors['accent_purple'],
                    font=('Arial', 20)).pack(side='left', padx=(0, 10))
            
            title_text = tk.Frame(title_container, bg=self.colors['bg_dark'])
            title_text.pack(side='left')
            
            tk.Label(title_text, text="单帧传送格式 · 码字生成工具", 
                    bg=self.colors['bg_dark'], fg=self.colors['text_primary'], 
                    font=('Microsoft YaHei', 18, 'bold')).pack(anchor='w')
            tk.Label(title_text, text="基于 CAN 2.0B 扩展帧协议  |  按《表4 单帧传送格式》规范生成", 
                    bg=self.colors['bg_dark'], fg=self.colors['text_muted'], 
                    font=('Microsoft YaHei', 9)).pack(anchor='w')
            
            divider = tk.Frame(main_frame, bg=self.colors['border'], height=1)
            divider.grid(row=1, column=0, columnspan=3, sticky='ew', pady=(0, 15))
            
            arb_card, arb_content = self.create_card(main_frame, "仲裁场（4字节）", row=2, column=0, sticky='nsew')
            
            self.entries = {}
            fields = [
                ("优先级 Priority", "ID[28:27] · 2bit · 0~3", "priority", 0, 3, 2),
                ("源节点地址 Source", "ID[26:21] · 6bit · 0~3F", "srcAddr", 1, 63, 6),
                ("组播标识 Multicast", "ID[20:19] · 2bit · 0~3", "multicast", 2, 3, 2),
                ("目的节点地址 Dest", "ID[18:13] · 6bit · 0~3F", "dstAddr", 3, 63, 6),
                ("帧序号标志 Seq Flag", "ID[12:11] · 2bit · 0~3", "seqFlag", 4, 3, 2),
                ("帧序号 Frame Seq", "ID[10:5] · 6bit · 0~3F", "frameSeq", 5, 63, 6),
                ("功能码 Function", "ID[4:0] · 5bit · 0~1F", "funcCode", 6, 31, 5),
            ]
            
            for label, bits, name, row, max_val, bit_width in fields:
                result = self.create_input_field(arb_content, label, bits, row, bit_width=bit_width)
                if isinstance(result, tuple):
                    entry, bin_label, bw = result
                    self.entries[name] = {'entry': entry, 'max': max_val, 'bin_label': bin_label, 'bit_width': bw}
                else:
                    self.entries[name] = {'entry': result, 'max': max_val}
            
            for name, info in self.entries.items():
                if name == 'seqFlag':
                    info['entry'].insert(0, '3')
                else:
                    info['entry'].insert(0, '0')
            
            sep_frame = tk.Frame(arb_content, bg=self.colors['bg_card'], height=20)
            sep_frame.pack(fill='x', pady=5)
            tk.Frame(sep_frame, bg=self.colors['border'], height=1).pack(fill='x', side='bottom')
            
            self.create_fixed_field(arb_content, "控制位 SRR/IDE/RTR", "SRR=1  IDE=1  RTR=0")
            
            ctrl_card, ctrl_content = self.create_card(main_frame, "控制场 + 数据场", row=2, column=1, sticky='nsew')
            
            self.create_fixed_field(ctrl_content, "保留位 r1/r0", "r1=0  r0=0 (固定)")
            
            dlc_container = tk.Frame(ctrl_content, bg=self.colors['bg_card'])
            dlc_container.pack(fill='x', pady=4)
            
            tk.Label(dlc_container, text="数据长度 DLC (1~8)", bg=self.colors['bg_card'], 
                    fg=self.colors['text_primary'],
                    font=('Microsoft YaHei', 10)).pack(anchor='w')
            
            dlc_row = tk.Frame(dlc_container, bg=self.colors['bg_card'])
            dlc_row.pack(fill='x', pady=(6, 0))
            
            self.dlc_var = tk.IntVar(value=4)
            dlc_slider = tk.Scale(dlc_row, from_=1, to=8, orient='horizontal',
                                  variable=self.dlc_var, command=self.on_dlc_change,
                                  bg=self.colors['bg_card'], fg=self.colors['accent_cyan'],
                                  highlightthickness=0, sliderrelief='flat',
                                  troughcolor=self.colors['bg_input'],
                                  activebackground=self.colors['accent_cyan'],
                                  font=('Consolas', 10), showvalue=False,
                                  length=150)
            dlc_slider.pack(side='left')
            
            self.dlc_label = tk.Label(dlc_row, text="4", bg=self.colors['bg_input'], 
                                      fg=self.colors['accent_cyan'],
                                      font=('Consolas', 16, 'bold'), width=3,
                                      highlightbackground=self.colors['accent_cyan'],
                                      highlightthickness=1)
            self.dlc_label.pack(side='left', padx=8)
            
            tk.Label(dlc_row, text="字节 (含SUM校验)", bg=self.colors['bg_card'], 
                    fg=self.colors['text_muted'],
                    font=('Microsoft YaHei', 8)).pack(side='left')
            
            sep_frame2 = tk.Frame(ctrl_content, bg=self.colors['bg_card'], height=15)
            sep_frame2.pack(fill='x', pady=5)
            tk.Frame(sep_frame2, bg=self.colors['border'], height=1).pack(fill='x', side='bottom')
            
            tk.Label(ctrl_content, text="信息数据包 Data Bytes", bg=self.colors['bg_card'], 
                    fg=self.colors['accent_cyan'],
                    font=('Microsoft YaHei', 10, 'bold')).pack(anchor='w')
            
            self.data_frame = tk.Frame(ctrl_content, bg=self.colors['bg_card'])
            self.data_frame.pack(fill='x', pady=(6, 0))
            self.data_entries = []
            self.build_data_entries(4)
            
            self.update_binary_display(trigger_generate=False)
            
            sep_frame3 = tk.Frame(ctrl_content, bg=self.colors['bg_card'], height=15)
            sep_frame3.pack(fill='x', pady=5)
            tk.Frame(sep_frame3, bg=self.colors['border'], height=1).pack(fill='x', side='bottom')
            
            sum_container = tk.Frame(ctrl_content, bg=self.colors['bg_card'])
            sum_container.pack(fill='x', pady=4)
            
            tk.Label(sum_container, text="校验字节 SUM", bg=self.colors['bg_card'], 
                    fg=self.colors['text_primary'],
                    font=('Microsoft YaHei', 10, 'bold')).pack(anchor='w')
            
            sum_row = tk.Frame(sum_container, bg=self.colors['bg_card'])
            sum_row.pack(fill='x', pady=(6, 0))
            
            tk.Label(sum_row, text="自动计算: Byte₀~Byteₙ₋₁ 累加和低字节", 
                    bg=self.colors['bg_card'], fg=self.colors['text_muted'],
                    font=('Microsoft YaHei', 8)).pack(side='left')
            
            self.sum_var = tk.StringVar(value="00")
            sum_entry = tk.Frame(sum_row, bg=self.colors['bg_input'],
                                highlightbackground=self.colors['accent_purple'],
                                highlightthickness=1)
            sum_entry.pack(side='right')
            tk.Entry(sum_entry, textvariable=self.sum_var, width=8, 
                    bg=self.colors['bg_input'], fg=self.colors['accent_purple'],
                    font=('Consolas', 14, 'bold'), state='readonly', justify='center',
                    relief='flat', bd=0).pack(padx=8, pady=6)
            
            output_card, output_content = self.create_card(main_frame, "生成结果", row=2, column=2, sticky='nsew')
            
            result_container = tk.Frame(output_content, bg=self.colors['bg_card'])
            result_container.pack(fill='x', pady=(0, 10))
            
            tk.Label(result_container, text="29位扩展标识符 (ID)", 
                    bg=self.colors['bg_card'], fg=self.colors['text_muted'],
                    font=('Microsoft YaHei', 9)).pack(anchor='w')
            
            self.id_output = tk.Label(result_container, text="等待输入...", 
                                      bg=self.colors['bg_input'], 
                                      fg=self.colors['accent_blue'],
                                      font=('Consolas', 15, 'bold'), 
                                      anchor='w', padx=10, pady=8,
                                      highlightbackground=self.colors['border'],
                                      highlightthickness=1)
            self.id_output.pack(fill='x', pady=(4, 8))
            
            tk.Label(result_container, text="完整帧十六进制码字", 
                    bg=self.colors['bg_card'], fg=self.colors['text_muted'],
                    font=('Microsoft YaHei', 9)).pack(anchor='w')
            
            self.frame_output = tk.Label(result_container, text="等待输入...", 
                                         bg=self.colors['bg_input'], 
                                         fg=self.colors['accent_cyan'],
                                         font=('Consolas', 18, 'bold'), 
                                         anchor='w', padx=10, pady=8,
                                         highlightbackground=self.colors['border'],
                                         highlightthickness=1)
            self.frame_output.pack(fill='x')
            
            byte_detail_label = tk.Label(output_content, text="字节分解 Byte Breakdown", 
                                          bg=self.colors['bg_card'], 
                                          fg=self.colors['accent_purple'],
                                          font=('Microsoft YaHei', 10, 'bold'))
            byte_detail_label.pack(anchor='w', pady=(10, 4))
            
            self.byte_table = scrolledtext.ScrolledText(output_content, height=12, width=50,
                                                        bg=self.colors['bg_input'], 
                                                        fg=self.colors['text_primary'],
                                                        font=('Consolas', 9), relief='flat',
                                                        state='disabled', padx=8, pady=8)
            self.byte_table.pack(fill='both', expand=True)
            
            btn_frame = tk.Frame(main_frame, bg=self.colors['bg_dark'])
            btn_frame.grid(row=3, column=0, columnspan=3, sticky='ew', pady=(15, 0))
            
            btn_container = tk.Frame(btn_frame, bg=self.colors['bg_dark'])
            btn_container.pack()
            
            self.create_button(btn_container, "◈ 生成码字", self.generate_frame,
                             self.colors['accent_blue'], self.colors['bg_dark'])
            self.create_button(btn_container, "◇ 复制结果", self.copy_result,
                             self.colors['bg_input'], self.colors['text_primary'])
            self.create_button(btn_container, "○ 重置", self.reset_all,
                             self.colors['bg_input'], self.colors['text_primary'])
            
            self.generate_frame()
            
        def create_button(self, parent, text, command, bg, fg):
            btn = tk.Frame(parent, bg=bg, relief='flat', 
                          highlightbackground=bg, highlightthickness=1)
            btn.pack(side='left', padx=5)
            
            btn_label = tk.Label(btn, text=text, bg=bg, fg=fg,
                                font=('Microsoft YaHei', 10, 'bold'),
                                padx=16, pady=8, cursor='hand2')
            btn_label.pack()
            
            btn_label.bind('<Enter>', lambda e: self.on_btn_hover(btn, btn_label, True))
            btn_label.bind('<Leave>', lambda e: self.on_btn_hover(btn, btn_label, False))
            btn_label.bind('<Button-1>', lambda e: command())
            
            return btn
        
        def on_btn_hover(self, btn_frame, label, entering):
            if entering:
                btn_frame.configure(highlightbackground=self.colors['accent_blue'],
                                  highlightthickness=1)
            else:
                btn_frame.configure(highlightbackground=label.cget('bg'),
                                  highlightthickness=1)
            
        def on_dlc_change(self, event=None):
            dlc = self.dlc_var.get()
            self.dlc_label.config(text=str(dlc))
            self.build_data_entries(dlc)
            
        def build_data_entries(self, dlc):
            for widget in self.data_frame.winfo_children():
                widget.destroy()
            self.data_entries = []
            
            user_count = max(0, dlc - 1)
            for i in range(user_count):
                row, col = i // 4, i % 4
                frame = tk.Frame(self.data_frame, bg=self.colors['bg_card'])
                frame.grid(row=row, column=col, padx=3, pady=3)
                
                tk.Label(frame, text=f"Byte{i}", bg=self.colors['bg_card'], 
                        fg=self.colors['text_muted'],
                        font=('Consolas', 8)).pack()
                
                input_frame = tk.Frame(frame, bg=self.colors['bg_input'],
                                      highlightbackground=self.colors['border'],
                                      highlightthickness=1)
                input_frame.pack()
                
                entry = tk.Entry(input_frame, width=6, bg=self.colors['bg_input'], 
                                fg=self.colors['accent_cyan'],
                                font=('Consolas', 11, 'bold'), justify='center',
                                insertbackground=self.colors['accent_cyan'],
                                relief='flat', bd=0)
                entry.pack(padx=4, pady=4)
                entry.insert(0, '00')
                entry.bind('<KeyRelease>', lambda e: self.generate_frame())
                entry.bind('<FocusIn>', lambda e: self.on_entry_focus(entry, True))
                entry.bind('<FocusOut>', lambda e: self.on_entry_focus(entry, False))
                self.data_entries.append(entry)
        
        def generate_frame(self, event=None):
            try:
                p = int(self.entries['priority']['entry'].get(), 16)
                s = int(self.entries['srcAddr']['entry'].get(), 16)
                m = int(self.entries['multicast']['entry'].get(), 16)
                d = int(self.entries['dstAddr']['entry'].get(), 16)
                seq_flag = int(self.entries['seqFlag']['entry'].get(), 16)
                f = int(self.entries['frameSeq']['entry'].get(), 16)
                fc = int(self.entries['funcCode']['entry'].get(), 16)
                dlc = self.dlc_var.get()
                
                data_bytes = []
                for entry in self.data_entries:
                    try:
                        val = int(entry.get(), 16)
                        data_bytes.append(val)
                    except ValueError:
                        data_bytes.append(0)
                
                id29, frame, sum_val = generate_frame(p, s, m, d, seq_flag, f, fc, dlc, data_bytes)
                
                self.id_output.config(text=f"0x{id29:08X}")
                self.frame_output.config(text=' '.join(f"{b:02X}" for b in frame))
                self.sum_var.set(f"{sum_val:02X}")
                
                self.byte_table.config(state='normal')
                self.byte_table.delete(1.0, 'end')
                
                lines = format_output(id29, frame, sum_val, verbose=True)
                self.byte_table.insert('end', lines)
                self.byte_table.config(state='disabled')
                
            except ValueError:
                pass
        
        def copy_result(self):
            text = self.frame_output.cget("text")
            if text and text != '-':
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                messagebox.showinfo("复制成功", "帧码字已复制到剪贴板")
            else:
                messagebox.showwarning("警告", "没有可复制的内容")
        
        def reset_all(self):
            for name, info in self.entries.items():
                if name == 'seqFlag':
                    info['entry'].delete(0, 'end')
                    info['entry'].insert(0, '3')
                else:
                    info['entry'].delete(0, 'end')
                    info['entry'].insert(0, '0')
            self.update_binary_display()
            self.dlc_var.set(4)
            self.dlc_label.config(text='4')
            self.build_data_entries(4)
            self.id_output.config(text='等待输入...')
            self.frame_output.config(text='等待输入...')
            self.sum_var.set('00')
            self.byte_table.config(state='normal')
            self.byte_table.delete(1.0, 'end')
            self.byte_table.config(state='disabled')
        
        def run(self):
            self.root.mainloop()
    
    app = CANFrameGenerator()
    app.run()


def main():
    """主入口"""
    if len(sys.argv) > 1:
        run_cli()
    else:
        run_gui()


if __name__ == '__main__':
    main()

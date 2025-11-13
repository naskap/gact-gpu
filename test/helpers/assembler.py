def assemble(assembly : str): 

    assembly = assembly.splitlines()

    opcodes = {
        'BRn'  : 0b0001,
        'CMP'  : 0b0010,
        'ADD'  : 0b0011,
        'SUB'  : 0b0100,
        'MUL'  : 0b0101,
        'DIV'  : 0b0110,
        'STR'  : 0b1000,
        'CONST': 0b1001,
        'LDR'  : 0b0111,
        'RET'  : 0b1111,
    }
    registers = {f'R{i}': i for i in range(16)}
    specials  = {'%blockIdx': 13, '%blockDim': 14, '%threadIdx': 15}
    registers.update(specials)
    
    labels  = {}
    program = []
    addr    = 0
    
    #   First pass      : collect labels
    for line in assembly: 
        # remove inline comments starting with ';'
        line = line.split(';', 1)[0].strip()
        # ignore empty lines and lines that start with '#'
        if not line: 
            continue
        if ':' in line: 
            label , _             = line.split(':', 1)
            labels[label.strip()] = addr
        else: 
            addr += 1
    
    addr = 0
    for line in assembly: 
        # remove inline comments starting with ';'
        line = line.split(';', 1)[0].strip()
        # ignore empty lines, comment lines starting with '#', and labels
        if not line or ':' in line: 
            continue
        parts    = line.replace(',', '').split()
        mnemonic = parts[0]
        if mnemonic not in opcodes: 
            raise ValueError(f"Unknown mnemonic: {mnemonic}")
        opcode = opcodes[mnemonic]
        if mnemonic in ['MUL', 'ADD', 'SUB', 'DIV']: 
            if len(parts) != 4: 
                raise ValueError(f"Invalid operands for {mnemonic}")
            dest = registers.get(parts[1])
            src1 = registers.get(parts[2])
            src2 = registers.get(parts[3])
            if dest is None or src1 is None or src2 is None: 
                raise ValueError(f"Invalid register in {line}")
            instr = (opcode << 12) | (dest << 8) | (src1 << 4) | src2
        elif mnemonic == 'CONST': 
            if len(parts) != 3 or not parts[2].startswith('#'): 
                raise ValueError(f"Invalid operands for {mnemonic}")
            dest = registers.get(parts[1])
            imm  = int(parts[2][1:])
            if dest is None or not (0 <= imm <= 255): 
                raise ValueError(f"Invalid operands in {line}")
            instr = (opcode << 12) | (dest << 8) | imm
        elif mnemonic == 'LDR': 
            if len(parts) != 3: 
                raise ValueError(f"Invalid operands for {mnemonic}")
            dest     = registers.get(parts[1])
            addr_reg = registers.get(parts[2])
            if dest is None or addr_reg is None: 
                raise ValueError(f"Invalid register in {line}")
            instr = (opcode << 12) | (dest << 8) | (addr_reg << 4)
        elif mnemonic == 'STR': 
            if len(parts) != 3: 
                raise ValueError(f"Invalid operands for {mnemonic}")
            addr_reg = registers.get(parts[1])
            val_reg  = registers.get(parts[2])
            if addr_reg is None or val_reg is None: 
                raise ValueError(f"Invalid register in {line}")
            instr = (opcode << 12) | (addr_reg << 4) | val_reg
        elif mnemonic == 'CMP': 
            if len(parts) != 3: 
                raise ValueError(f"Invalid operands for {mnemonic}")
            reg1 = registers.get(parts[1])
            reg2 = registers.get(parts[2])
            if reg1 is None or reg2 is None: 
                raise ValueError(f"Invalid register in {line}")
            instr = (opcode << 12) | (reg1 << 4) | reg2
        elif mnemonic == 'BRn': 
            if len(parts) != 2: 
                raise ValueError(f"Invalid operands for {mnemonic}")
            label = parts[1]
            if label not in labels: 
                raise ValueError(f"Undefined label: {label}")

            instr = (opcode << 12) | (0b1000 << 8) | (labels[label] & 0xFF)
        elif mnemonic == 'RET': 
            if len(parts) != 1: 
                raise ValueError(f"Invalid operands for {mnemonic}")
            instr = opcode << 12
        else: 
            raise ValueError(f"Unsupported mnemonic: {mnemonic}")
        program.append(instr)
        addr += 1
    return program
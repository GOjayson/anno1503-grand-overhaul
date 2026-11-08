"""Pure AMD64 central diplomacy bridge shared by overlay and transient activation."""
import struct
HOOK=0xdf460
RESUME=0xdf466
BEFORE=bytes.fromhex('488bc4895010')
LEAF_UNWIND=bytes.fromhex('01000000')
class Code:
 def __init__(self,rva):self.rva=rva;self.bytes=bytearray();self.labels={};self.fixups=[]
 def add(self,value):self.bytes.extend(bytes.fromhex(value) if isinstance(value,str) else value)
 def mark(self,name):self.labels[name]=self.rva+len(self.bytes)
 def branch(self,opcode,target):
  self.add(opcode);at=len(self.bytes);self.add(bytes(4));self.fixups.append((at,target))
 def finish(self):
  for at,target in self.fixups:
   dest=self.labels[target] if isinstance(target,str) else target
   struct.pack_into('<i',self.bytes,at,dest-self.rva-at-4)
  return bytes(self.bytes)

def gate(c):
 c.add('83 fa 02');c.branch('0f85','native')
 c.add('41 83 f8 03');c.branch('0f85','native')
 c.add('4d 85 c9');c.branch('0f84','native')
 c.add('48 8d 05');c.add(struct.pack('<i',0xfabe0-(c.rva+len(c.bytes)+4)))
 c.add('49 39 01');c.branch('0f85','native')
 c.add('66 41 83 b9 9c 00 00 00 0c');c.branch('0f85','native')
 c.add('4d 8b 59 18 4d 85 db');c.branch('0f84','native')
 c.add('41 83 bb 4c 0a 00 00 0c');c.branch('0f85','native')
 c.add('41 8b 83 b8 0a 00 00 41 89 c2 41 81 e2 00 00 ff ff')
 c.add('41 81 fa 00 00 53 57');c.branch('0f85','native')
 # Once a tagged ordinary CPU is identified, broken owner/world identity is
 # denied rather than permitting a declaration through a stale controller.
 c.add('49 39 49 10');c.branch('0f85','deny')
 c.add('49 39 4b 08');c.branch('0f85','deny')
 c.add('45 8b 51 08 41 83 fa 1f');c.branch('0f87','deny')
 # Keep the initiating player in R9 unchanged for native processing.
 c.add('45 0f b7 93 64 0a 00 00 45 3b 51 08');c.branch('0f85','deny')
 # Validate the source's exact native player-table identity. RAX policy word
 # is reloaded afterward; R9 remains the initiating player for the native call.
 c.add('48 8b 81 10 02 00 00 48 85 c0');c.branch('0f84','deny')
 c.add('4e 39 4c d0 08');c.branch('0f85','deny')
 # Actual native GetDiplomacyState(type=2,target) reads this byte after
 # resolving target->GetId(). Existing reciprocal war is a defense/update,
 # not a new initiation, and must not consume the declaration cadence.
 c.add('4c 8b 5c 24 28 4d 85 db');c.branch('0f84','deny')
 c.add('48 8d 05');c.add(struct.pack('<i',0xfabe0-(c.rva+len(c.bytes)+4)))
 c.add('49 39 03');c.branch('0f85','deny')
 c.add('49 39 4b 10');c.branch('0f85','deny')
 c.add('45 8b 53 08 41 83 fa 1f');c.branch('0f87','deny')
 c.add('48 8b 81 10 02 00 00 4e 39 5c d0 08');c.branch('0f85','deny')
 c.add('4f 8d 14 52 43 80 bc 51 da 01 00 00 03');c.branch('0f87','deny')
 c.add('43 80 bc 51 da 01 00 00 00');c.branch('0f85','native')
 c.add('4d 8b 59 18') # restore controller after target identity lookup
 c.add('41 8b 83 b8 0a 00 00 41 89 c2 41 c1 ea 08 41 83 e2 03')
 c.branch('0f84','deny')
 c.add('41 89 c2 41 c1 ea 0a 41 ff c2 41 83 e2 3f')
 c.add('25 ff 03 ff ff 41 c1 e2 0a 44 09 d0 41 89 83 b8 0a 00 00')
 c.add('41 89 c2 41 c1 ea 08 41 83 e2 03 41 83 fa 03');c.branch('0f84','native')
 c.add('41 83 fa 02');c.branch('0f84','medium')
 c.add('a9 00 0c 00 00');c.branch('0f85','deny');c.branch('e9','native')
 c.mark('medium');c.add('a9 00 04 00 00');c.branch('0f85','deny')
 c.mark('native');c.add('48 8b c4 89 50 10');c.branch('e9',RESUME)
 c.mark('deny');c.add('31 c0 c3')

def build_world_policy_code(rva=0):
 c=Code(rva);gate(c);code=c.finish()
 return code,dict(entry=rva,end=rva+len(code),world_policy=rva,world_policy_end=rva+len(code))

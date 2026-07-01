from ...components.denali.psu import DenaliPsuSlotDesc
from ...components.denali.supervisor import DenaliSupervisor
from ...components.microsemi import MicrosemiPortDesc


class OtterLakeShim(DenaliSupervisor):

   UPSTREAM_PORT = MicrosemiPortDesc(
      port=8,
      dsp=0,
      partition=0,
      name="cpu",
      upstream=True
   )

   LINECARD_PORTS = [
      MicrosemiPortDesc(port=32, dsp=8, partition=0, name="lc3"),
      MicrosemiPortDesc(port=33, dsp=9, partition=0, name="lc4"),
      MicrosemiPortDesc(port=34, dsp=10, partition=0, name="lc5"),
      MicrosemiPortDesc(port=35, dsp=11, partition=0, name="lc6"),
      MicrosemiPortDesc(port=36, dsp=12, partition=0, name="lc7"),
      MicrosemiPortDesc(port=37, dsp=13, partition=0, name="lc8"),
      MicrosemiPortDesc(port=38, dsp=14, partition=0, name="lc9"),
      MicrosemiPortDesc(port=39, dsp=15, partition=0, name="lc10"),
   ]

   FABRIC_PORTS = [
      MicrosemiPortDesc(port=24, dsp=1, partition=0, name="fc1"),
      MicrosemiPortDesc(port=25, dsp=2, partition=0, name="fc2"),
      MicrosemiPortDesc(port=26, dsp=3, partition=0, name="fc3"),
      MicrosemiPortDesc(port=27, dsp=4, partition=0, name="fc4"),
      MicrosemiPortDesc(port=28, dsp=5, partition=0, name="fc5"),
      MicrosemiPortDesc(port=29, dsp=6, partition=0, name="fc6"),
   ]

   PSUS = [
      DenaliPsuSlotDesc(psuId=1, bank=1, slot=1, bus=16, addr=0x70),
      DenaliPsuSlotDesc(psuId=2, bank=1, slot=2, bus=16, addr=0x71),
      DenaliPsuSlotDesc(psuId=3, bank=1, slot=3, bus=16, addr=0x72),
      DenaliPsuSlotDesc(psuId=4, bank=1, slot=4, bus=17, addr=0x70),
      DenaliPsuSlotDesc(psuId=5, bank=1, slot=5, bus=17, addr=0x71),
      DenaliPsuSlotDesc(psuId=6, bank=1, slot=6, bus=17, addr=0x72),
      DenaliPsuSlotDesc(psuId=7, bank=2, slot=1, bus=18, addr=0x70),
      DenaliPsuSlotDesc(psuId=8, bank=2, slot=2, bus=18, addr=0x71),
      DenaliPsuSlotDesc(psuId=9, bank=2, slot=3, bus=18, addr=0x72),
      DenaliPsuSlotDesc(psuId=10, bank=2, slot=4, bus=19, addr=0x70),
      DenaliPsuSlotDesc(psuId=11, bank=2, slot=5, bus=19, addr=0x71),
      DenaliPsuSlotDesc(psuId=12, bank=2, slot=6, bus=19, addr=0x72),
   ]

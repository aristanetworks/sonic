from ..core.fixed import FixedChassis, FixedSystem
from ..core.hwapi import HwApi
from ..core.platform import registerPlatform
from ..core.port import PortLayout
from ..core.psu import PsuSlot
from ..core.types import I2cAddr, PciAddr
from ..core.utils import incrange

from ..components.asic.xgs.trident3 import Trident3X2
from ..components.psu.fixed import Fixed100AC
from ..components.scd import Scd, ScdCause
from ..components.vrm import Vrm, VrmDetector
from ..components.vrm.sic450 import Sic450
from ..components.vrm.tps549d22 import Tps549D22

from ..descs.fan import FanDesc, FanPosition
from ..descs.gpio import GpioDesc
from ..descs.reset import ResetDesc
from ..descs.xcvr import Rj45, Sfp

from .cpu.prairie import PrairieCpu

class PikeZ1PChassis(FixedChassis):
    FAN_SLOTS = 1
    FAN_COUNT = 2
    PSU_SLOTS = 1

class PikeZ2PChassis(PikeZ1PChassis):
    PSU_SLOTS = 2

class PikeZ(FixedSystem):

    PORTS = PortLayout(
        (Rj45(i) for i in incrange(1, 48)),
        (Sfp(i) for i in incrange(49, 52)),
    )

    def __init__(self):
        super().__init__()

        self.cpu = self.newComponent(PrairieCpu)
        port = self.cpu.getPciPort(0)
        scd = port.newComponent(Scd, addr=port.addr)
        self.scd = scd
        scd.createWatchdog()
        scd.createPowerCycle()
        scd.addSmbusMasterRange(0x8000, 0, 0x80, bus=5)
        # TODO: Add reporting for -R fans
        scd.addFanGroup(0x2000, 4, self.CHASSIS.FAN_SLOTS, self.CHASSIS.FAN_COUNT)
        for i in incrange(1, self.CHASSIS.FAN_COUNT):
            desc = FanDesc(i, position=FanPosition.OUTLET)
            scd.addFan(desc)

        scd.addReloadCauseProvider(addr=0x5010, causes=[
            ScdCause(0x00, ScdCause.POWERLOSS),
            ScdCause(0x02, ScdCause.WATCHDOG),
            ScdCause(0x03, ScdCause.REBOOT, 'Button hard reset'),
            ScdCause(0x04, ScdCause.RAIL, 'POS0V8'),
            ScdCause(0x05, ScdCause.RAIL, 'POS1V2'),
            ScdCause(0x06, ScdCause.RAIL, 'POS1V8'),
            ScdCause(0x07, ScdCause.RAIL, 'CPU_SLP_S3'),
            ScdCause(0x08, ScdCause.RAIL, 'POS0V88'),
            ScdCause(0x09, ScdCause.RAIL, 'POS0V8'),
            ScdCause(0x0a, ScdCause.RAIL, 'POS1V8'),
            ScdCause(0x0b, ScdCause.RAIL, 'CPU_3V3'),
            ScdCause(0x0c, ScdCause.REBOOT, 'Button factory reset'),
            ScdCause(0x0d, ScdCause.RAIL, 'APU_VRM'),
            ScdCause(0x0e, ScdCause.OVERTEMP),
            ScdCause(0x0f, ScdCause.REBOOT, 'Software Reboot'),
            ScdCause(0x10, ScdCause.KILLSWITCH),
        ])

        scd.addResets([
            ResetDesc('ext_mux_reset', addr=0x4000, bit=8),
            ResetDesc('phy_reset', addr=0x4000, bit=7),
            ResetDesc('link_flap_reset', addr=0x4000, bit=6),
            ResetDesc('cpu_reset', addr=0x4000, bit=2),
            ResetDesc('switch_chip_reset', addr=0x4000, bit=1, auto=False),
            ResetDesc('switch_chip_pcie_reset', addr=0x4000, bit=0, auto=False),
        ])

        scd.addLeds([
            (0x6040, 'beacon'),
            (0x6050, 'status'),
            (0x6060, 'fan_status'),
            (0x6070, 'psu_status'),
            (0x6080, 'cloud'),
            (0x6090, 'link'),
            (0x60A0, 'poe'),
            (0x60B0, 'speed'),
        ])

        for psuId in incrange(1, self.CHASSIS.PSU_SLOTS):
            name = "psu%d" % psuId
            statusGpio = scd.addGpio(
                GpioDesc("%s_status" % name, 0x5000, 7 + psuId, ro=True)
            )
            scd.newComponent(
                PsuSlot,
                slotId=psuId,
                presentGpio=True,
                inputOkGpio=statusGpio,
                outputOkGpio=statusGpio,
                forcePsuLoad=True,
                psus=[
                    Fixed100AC,
                ]
            )

        intrRegs = [
            scd.createInterrupt(addr=0x3000, num=0),
        ]

        scd.addXcvrSlots(
            ports=self.PORTS.getEthernets(),
            ledAddr=0x6190,
        )

        scd.addXcvrSlots(
            ports=self.PORTS.getSfps(),
            addr=0xA010,
            bus=0,
            ledAddr=0x6100,
            intrRegs=intrRegs,
            intrRegIdxFn=lambda xcvrId: 0,
            intrBitFn=lambda xcvrId: 5 + xcvrId - 49
        )

        addr = I2cAddr(0, 0x14)
        vouts, uvs = ({
                800: 0x0118, # 0.805V
                825: 0x0120, # 0.828V
                850: 0x0128, # 0.851V
                875: 0x0130, # 0.876V
            },
            (0x00FC, 0x00BE),
        ) if self.getHwApi() >= HwApi(3) else ({
                800: 0x019a, # 0.800V
                825: 0x01a6, # 0.825V
                850: 0x01b3, # 0.850V
                875: 0x01c0, # 0.875V
            },
            (0x0170, 0x0116),
        )
        vrm = VrmDetector([
            self.newComponent(Tps549D22, addr=addr, vouts={
                800: 0x0175, # 0.804V
                825: 0x0180, # 0.828V
                850: 0x018C, # 0.854V
                875: 0x0196, # 0.875V
            }),
            self.newComponent(Sic450, addr=addr, vouts=vouts, uvs=uvs)
        ])

        port = self.cpu.getPciPort(1)
        port.newComponent(Trident3X2, addr=port.addr,
            coreResets=[
                scd.inventory.getReset('switch_chip_reset'),
            ],
            pcieResets=[
                scd.inventory.getReset('switch_chip_pcie_reset'),
            ],
            quirks=[
                Trident3X2.AvsQuirk(vrm),
            ],
        )

@registerPlatform()
class PikeZF(PikeZ):

    CHASSIS = PikeZ1PChassis

    SID = ['PikeIslandZ-F']
    SKU = ['CCS-720DT-48S-F']

@registerPlatform()
class PikeZ2F(PikeZ):

    CHASSIS = PikeZ2PChassis

    SID = ['PikeIslandZ', 'PikeIslandZ-2F']
    SKU = ['CCS-720DT-48S', 'CCS-720DT-48S-2F']

@registerPlatform()
class PikeZR(PikeZ):

    CHASSIS = PikeZ1PChassis

    SID = ['PikeIslandZ-R']
    SKU = ['CCS-720DT-48S-R']

@registerPlatform()
class PikeZ2R(PikeZ):

    CHASSIS = PikeZ2PChassis

    SID = ['PikeIslandZ-2R']
    SKU = ['CCS-720DT-48S-2R']

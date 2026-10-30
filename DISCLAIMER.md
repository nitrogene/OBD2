# Automotive Safety Disclaimer & Limitation of Liability

---

> [!CAUTION]
> **FOR EDUCATIONAL, RESEARCH, AND HOBBYIST EXPERIMENTATION PURPOSES ONLY**
> This repository (including schematics, PCB layouts, bills of materials, manufacturing archives, firmware specifications, and documentation) is provided free of charge for educational, research, and hobbyist experimentation purposes only.

### 1. Automotive Multiplexing & Electrical Safety Warnings
Interfacing non-OEM DIY hardware with a motor vehicle's On-Board Diagnostics port (SAE J1962 / OBD-II) carries inherent electrical and operational hazards:
* **Bus Disturbance:** Unintended signals, bus loading, or communication faults on multiplexed networks (CAN High-Speed, ISO 9141-2 K-Line) may interfere with the normal operation of critical vehicle control units (ECU, TCM, ABS/ESP, instrument cluster, airbags, power steering).
* **Electrical Transients:** Automotive power nets are subject to severe electrical disturbances (cranking dips, load-dump spikes up to 40V–60V, inductive transients ISO 7637-2). Incorrect wiring or component failure risks short circuits, thermal overload, parasitic battery drain, or permanent electronic damage.
* **Regulatory & Warranty Implications:** Connecting uncertified equipment may void manufacturer vehicle warranties or violate local road safety and vehicle inspection regulations.

### 2. Disclaimer of Warranties and Limitation of Liability
* **"AS IS" BASIS:** THE HARDWARE DESIGNS, DOCUMENTATION, AND ASSOCIATED SOFTWARE TOOLS ARE PROVIDED ON AN "AS IS" AND "AS AVAILABLE" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING, WITHOUT LIMITATION, ANY WARRANTIES OR CONDITIONS OF TITLE, NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
* **NO LIABILITY:** IN NO EVENT SHALL THE AUTHORS, COPYRIGHT HOLDERS, OR CONTRIBUTORS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT (INCLUDING NEGLIGENCE), OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE HARDWARE, ITS REPLICATION, ASSEMBLY, SOLDERING, FLASHOVER, VEHICULAR INTERFACING, OR THE INABILITY TO USE THE DESIGNS DESCRIBED IN THIS REPOSITORY. THIS INCLUDES, WITHOUT LIMITATION, VEHICULAR DAMAGE, ELECTRONIC SYSTEM MALFUNCTION, ACCIDENTS, BODILY INJURY, LOSS OF LIFE, OR MONETARY LOSS.
* **USER SOLE RESPONSIBILITY:** ANY FABRICATION, ASSEMBLY, SOLDERING, BENCH POWERING, ROAD TESTING, AND VEHICLE CONNECTION IS UNDERTAKEN AT THE SOLE RISK AND DISCRETION OF THE USER. THE USER IS SOLELY RESPONSIBLE FOR COMPLYING WITH APPLICABLE TRANSPORT REGULATIONS AND MUST NEVER ATTEMPT TO INTERACT WITH DIAGNOSTIC EQUIPMENT WHILE DRIVING WITHOUT A DEDICATED PASSENGER OPERATOR.

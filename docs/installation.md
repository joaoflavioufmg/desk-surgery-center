# DESK — Discrete Event Simulation Kit

## 🚀 Getting Started

### Installation

## 🛠️ Requirements

* Python >= 3.11
* simpy == 4.1.1
* numpy == 2.2.6
* pandas == 2.3.1
* scipy == 1.15.3
* matplotlib == 3.10.5

**Optional (for process mining):**

* R >= 4.0
* BupaR
* processanimateR

### Installation

🪟 Windows (PowerShell / VS Code / Cursor )

*1) Clone the DESK repository*
```bash
git clone https://github.com/joaoflavioufmg/desk.git
```

*2) Enter the project directory*
```bash
cd desk
```

*3) Create a virtual environment*
```bash
py -m venv venv
```

*4) Allow PowerShell to activate virtual environments (run once per machine)*
```bash
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

*5) Activate the virtual environment*
```bash
.\venv\Scripts\Activate.ps1
```

*6) Upgrade pip inside the virtual environment*
```bash
py -m pip install --upgrade pip
```

*7) Install DESK and its dependencies*
```bash
pip install .
```

*8) Verify that DESK and DESK-DISTFIT were installed correctly*
```bash
desk-sim -h
```
```bash
desk-distfit -h
```

*9) Run the hospital example with visualization*
```bash
desk-sim -m examples/hospital.py --mode visualization
```

*10) Run desk-distfit with some data*
```bash
desk-distfit -d input_data/data10.txt
```

🐧 Linux / macOS (Terminal)

*1) Clone the DESK repository*
```bash
git clone https://github.com/joaoflavioufmg/desk.git
```

*2) Enter the project directory*
```bash
cd desk
```

*3) Create a virtual environment*
```bash
python -m venv venv
```

*4) Activate the virtual environment*
```bash
source venv/bin/activate
```

*5) Upgrade pip inside the virtual environment*
```bash
python -m pip install --upgrade pip
```

*6) Install DESK and its dependencies*
```bash
pip install .
```

*7) Verify that DESK and DESK-DISTFIT were installed correctly*
```bash
desk-sim -h
```
```bash
desk-distfit -h
```

*8) Run the hospital example with visualization*
```bash
desk-sim -m examples/hospital.py --mode visualization
```

*9) Run desk-distfit with some data*
```bash
desk-distfit -d input_data/data10.txt
```
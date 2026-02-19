
import psutil
import platform
import os
import json
import time

class TaskManager:
    def __init__(self):
        # Whitelist of critical system processes (Windows)
        self.WHITELIST = [
            "System Idle Process", "System", "Registry",
            "smss.exe", "csrss.exe", "wininit.exe", "services.exe",
            "lsass.exe", "svchost.exe", "fontdrvhost.exe", "Memory Compression",
            "spoolsv.exe", "dwm.exe", "explorer.exe", "winlogon.exe",
            "atieclxx.exe", "MpCmdRun.exe", "NisSrv.exe", "MsMpEng.exe",
            "SearchIndexer.exe", "RuntimeBroker.exe", "sihost.exe",
            "taskhostw.exe", "audiodg.exe", "ctfmon.exe"
        ]
        
    def get_system_status(self):
        """Returns JSON status of CPU, RAM, Battery, GPU, Disk, and Uptime."""
        # CPU Usage
        cpu_usage = psutil.cpu_percent(interval=None)
        if cpu_usage == 0.0:
             cpu_usage = psutil.cpu_percent(interval=0.1)
             
        ram = psutil.virtual_memory()
        
        # GPU Check (NVIDIA)
        gpu_info = "N/A"
        try:
            import subprocess
            cmd = "nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,memory.used,memory.total --format=csv,noheader,nounits"
            output = subprocess.check_output(cmd, shell=True).decode().strip()
            if output:
                util, temp, mem_used, mem_total = output.split(', ')
                gpu_info = f"NVIDIA: %{util} ({temp}°C) | VRAM: {mem_used}MB / {mem_total}MB"
        except:
            gpu_info = "GPU verisi alınamadı"

        # CPU Temperature (Windows WMI / PowerShell)
        cpu_temp = "N/A"
        try:
            # Try WMI via PowerShell (often works if run as admin or depending on bios)
            # This is complex on Windows. 'wmic' is deprecated but usually works.
            # Using ComputerInfo often requires admin.
            # For now, let's try a common WMI query if python 'wmi' lib is present, else skip.
            import wmi
            w = wmi.WMI(namespace="root\\wmi")
            temps = w.MSAcpi_ThermalZoneTemperature()
            if temps:
                # Kelvin to Celcius
                t = temps[0].CurrentTemperature
                cpu_temp = f"{(t - 2732) / 10.0}°C"
        except:
             # Fallback: OpenHardwareMonitor? Too complex.
             # Fallback psutil sensors (usually linux only but sometimes works)
             if not cpu_temp or cpu_temp == "N/A":
                 try:
                    stats = psutil.sensors_temperatures()
                    if 'coretemp' in stats:
                        cpu_temp = f"{stats['coretemp'][0].current}°C"
                 except: pass

        # Uptime
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        uptime_hours = int(uptime_seconds // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)
        uptime_str = f"{uptime_hours} Saat {uptime_minutes} Dakika"

        # Disks
        disk_info = []
        for partition in psutil.disk_partitions():
            try:
                if 'cdrom' in partition.opts or partition.fstype == '': continue
                usage = psutil.disk_usage(partition.mountpoint)
                free_gb = round(usage.free / (1024**3), 1)
                total_gb = round(usage.total / (1024**3), 1)
                percent = usage.percent
                disk_info.append(f"{partition.device} (%{percent} Dolu) - {free_gb} GB Boş / {total_gb} GB")
            except: pass
        
        # RAM Temp is usually not available via standard APIs without specific motherboard drivers/tools (e.g. iCUE, HWMonitor).
        # We will skip RAM Temp to avoid false data.

        battery = "AC Power"
        try:
            bat = psutil.sensors_battery()
            if bat:
                plugged = "PLUGGED" if bat.power_plugged else "BATTERY"
                battery = f"{bat.percent}% ({plugged})"
        except:
            pass

        return {
            "cpu_percent": cpu_usage,
            "cpu_temp": cpu_temp,
            "ram_percent": ram.percent,
            "ram_used_gb": round(ram.used / (1024**3), 2),
            "ram_total_gb": round(ram.total / (1024**3), 2),
            "gpu": gpu_info,
            "uptime": uptime_str,
            "disks": disk_info,
            "battery": battery
        }

    def get_resource_hogs(self, limit=5):
        """Returns top RAM/CPU consumers."""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent']):
            try:
                # Calculate Memory
                mem_mb = round(proc.info['memory_info'].rss / (1024 * 1024), 2)
                
                # CPU percent (needs interval usually, here just instant snapshot might be low, but okay for general)
                # psutil.process_iter cpu_percent is since last call, first call is 0. 
                # To be better, we might need to sleep or trust ongoing monitoring.
                # For now, memory is more reliable instantly.
                
                processes.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "memory_mb": mem_mb,
                    "cpu_percent": proc.info['cpu_percent']
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        # Sort by Memory Usage
        sorted_procs = sorted(processes, key=lambda p: p['memory_info']['rss'] if 'memory_info' in p else p['memory_mb'], reverse=True)
        return sorted_procs[:limit]

    def optimize_performance(self):
        """Suggests apps to close for Game Mode."""
        targets = ["chrome.exe", "firefox.exe", "msedge.exe", "discord.exe", "spotify.exe", "steamwebhelper.exe", "teams.exe"]
        found = []
        
        total_ram_freed = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
            try:
                name = proc.info['name'].lower()
                if name in targets:
                    mem_mb = round(proc.info['memory_info'].rss / (1024 * 1024), 2)
                    found.append({
                        "pid": proc.info['pid'],
                        "name": proc.info['name'],
                        "memory_mb": mem_mb
                    })
                    total_ram_freed += mem_mb
            except:
                pass
                
        return {
            "candidates": found,
            "total_potential_freed_mb": round(total_ram_freed, 2)
        }

    def kill_process(self, process_name):
        """Safely kills a process by name if not whitelisted."""
        if process_name in self.WHITELIST:
            return {"status": "error", "message": f"❌ {process_name} kritik bir sistem dostudur, kapatılamaz!"}
            
        killed_count = 0
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'].lower() == process_name.lower():
                    pid = proc.info['pid']
                    p = psutil.Process(pid)
                    p.terminate()
                    killed_count += 1
            
            if killed_count > 0:
                return {"status": "success", "message": f"✅ {killed_count} adet {process_name} işlemi sonlandırıldı."}
            else:
                return {"status": "warning", "message": f"⚠️ {process_name} çalışmıyor."}
                
        except Exception as e:
            return {"status": "error", "message": f"Hata: {str(e)}"}

    def _get_folder_size(self, folder):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(folder):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try: total_size += os.path.getsize(fp)
                except: pass
        return round(total_size / (1024**3), 2)
        
    def analyze_disk_usage(self):
        """Returns major space consumers in User Profile."""
        base = os.environ['USERPROFILE']
        common_heavy_folders = [
            "Downloads", "Documents", "Desktop", "Videos", "Pictures", 
            "AppData\\Local\\Temp", "AppData\\Local\\Google\\Chrome\\User Data"
        ]
        
        report = []
        for folder in common_heavy_folders:
            path = os.path.join(base, folder)
            if os.path.exists(path):
                size = self._get_folder_size(path)
                if size > 0.1: # Only report > 100MB
                    report.append({"path": folder, "size_gb": size})
                    
        report.sort(key=lambda x: x['size_gb'], reverse=True)
        return report

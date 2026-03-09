import os
import json
import random
from datetime import datetime, timedelta

def main():
    print("Gerando dados de teste...")
    
    net_dir = os.path.join(os.path.dirname(__file__), "mock_network")
    if not os.path.exists(net_dir):
        os.makedirs(net_dir)
        
    start_date = datetime(2026, 1, 1)
    
    users = [
        {"name": "Leonardo Scherpl", "machine": "PC-LEO"},
        {"name": "Ana Souza", "machine": "PC-ANA"},
        {"name": "Carlos TI", "machine": "PC-CARLOS"}
    ]
    
    for i in range(30):
        current_date = start_date + timedelta(days=i)
        if current_date.weekday() >= 5: # Pula fim de semana
            continue
            
        date_str = current_date.strftime("%Y-%m-%d")
        
        for u in users:
            user_dir = os.path.join(net_dir, u["machine"])
            if not os.path.exists(user_dir):
                os.makedirs(user_dir)
                
            file_path = os.path.join(user_dir, f"{u['machine']}_{date_str}.json")
            
            # Lógica Mock direcionada para Banco de Horas
            # Leonardo sempre chega atrasado
            if u["name"] == "Leonardo Scherpl":
                start_hour = 8
                start_min = random.randint(30, 59) # Atrasado
                jornada_h = random.uniform(7.5, 8.5) # Faltando horas
                a_pct = random.uniform(0.60, 0.70)
                l_pct = random.uniform(0.10, 0.25)
            # Ana sempre faz hora extra
            elif u["name"] == "Ana Souza":
                start_hour = 7
                start_min = random.randint(0, 30) # Adiantada
                jornada_h = random.uniform(9.5, 10.5) # Hora extra
                a_pct = random.uniform(0.85, 0.95)
                l_pct = random.uniform(0.01, 0.05)
            # Carlos trabalha certinho
            else:
                start_hour = 8
                start_min = 0 # Pontual
                jornada_h = 10.0 # Bate ponto 18h redondo (10h passadas)
                a_pct = random.uniform(0.80, 0.90)
                l_pct = random.uniform(0.05, 0.10)
                
            session_start = current_date.replace(hour=start_hour, minute=start_min, second=0)
            session_end = session_start + timedelta(hours=jornada_h)
            
            total_seconds = int(jornada_h * 3600)
            
            i_pct = 1.0 - (a_pct + l_pct)
            act_s = int(total_seconds * a_pct)
            lck_s = int(total_seconds * l_pct)
            idl_s = int(total_seconds * i_pct)
            
            # Alguns eventos falsos p/ Gantt
            e_start = session_start.isoformat()
            e_end = (session_start + timedelta(seconds=act_s)).isoformat()
            
            data = {
                "operator_name": u["name"],
                "machine": u["machine"],
                "username": u["name"].split()[0].lower(),
                "date": date_str,
                "version": "1.3",
                "events": [
                    {"type": "boot", "timestamp": session_start.isoformat()},
                    {"type": "active", "start": e_start, "end": e_end, "duration_seconds": act_s},
                    {"type": "shutdown", "timestamp": session_end.isoformat()}
                ],
                "summary": {
                    "active_seconds": act_s,
                    "idle_seconds": idl_s,
                    "locked_seconds": lck_s,
                    "session_start": session_start.isoformat(),
                    "session_end": session_end.isoformat()
                }
            }
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Mock Data gerado com sucesso em: {net_dir}")
    print("Mude o config.py temporariamente para apontar para essa pasta se quiser testar o Dashboard!")

if __name__ == "__main__":
    main()

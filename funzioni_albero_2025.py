import requests
import os
from dotenv import load_dotenv
from fuzzywuzzy import process
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from datetime import datetime
from langchain_openai import ChatOpenAI
import pytz


load_dotenv()
odoo_url = "https://dev-unitiva.odoo.com/"
username = os.getenv("user")
pw = os.getenv('pw')
db = os.getenv('db')
api_key= os.getenv('openai_key')

llm = ChatOpenAI(
    api_key=api_key,
    model='gpt-4o',
    temperature=0
)

# Modelli che richiedono employee_id
modelli_con_employee_id = [
    "hr.leave",          # Richieste di ferie
    "hr.attendance",     # Presenze giornaliere
    "hr.contract",       # Contratti dipendenti
    "hr.expense",        # Note spese
    "account.analytic.line",  # Fogli ore legati ai dipendenti
    "hr.payslip",        # Buste paga
    "hr.skill",          # Competenze del dipendente
    "hr.employee.public", # Record dipendenti pubblici (ridotto)
]

# Modelli che richiedono uid
modelli_con_uid = [
    "res.users",         # Dati relativi all'utente
    "calendar.event",    # Eventi in calendario assegnati all'utente
    "mail.activity",     # Attività pianificate dall'utente
    "res.partner",       # Partner e contatti collegati all'utente
    "crm.lead",          # Opportunità di vendita (CRM)
    "helpdesk.ticket",  # Ticket di supporto assegnati
    'project.project'
]

id_ferie = {
    "Ferie": 1,
    "Malattia": 2,
    "Non retribuite": 4,
    "Permesso 104": 6,
    "Congedo parentale": 7,
    "Permesso da Compensare (per tirocini e stagisti max 2h/mese)": 9,
    "Congedo matrimoniale": 10,
    "Permesso visita medica": 11,
    "Permesso studio": 12,
    "Permessi Ex-fest.": 13,
    "Permessi ROL": 14,
    "Permesso per Lutto": 15,
    "Giorni di compensazione": 16,
    "Congedo di Maternità": 17  
    }

# Imposta il fuso orario (ad esempio 'Europe/Rome')
timezone = pytz.timezone('Europe/Rome')

# Ottieni la data e ora correnti
current_time = datetime.now(timezone)

# Formatta la data nel formato richiesto
formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")

#METODO PER EFFETTURA AUTENTICAZIONE SU ODOO (OK)
def autenticazione():
    url_auth = f"{odoo_url}/web/session/authenticate"
    payload_auth = {
        "jsonrpc": "2.0",
        "params": {
            "db":db,
            "login": username,
            "password": pw
        }
    }
    #effettua richiesta
    session = requests.Session()
    response_auth = session.post(url_auth, json=payload_auth)
    response_auth.raise_for_status()
    result = response_auth.json()
    try:
        uid = result['result']['uid']
    except Exception as e:
        return "Autenticazione fallita"
    
    return uid,session

#METODO PER TROVARE IL NOME CORRETTO DI UN PROGETTO (OK)
def find_project(project_name):
    #autenticazione
    uid,session = autenticazione()
    # URL per cercare il dipendente
    url_employee = f"{odoo_url}/web/dataset/call_kw/hr.employee/search_read"
    payload_employee = {
        "jsonrpc": "2.0",
        "method": "call",
        "id": 1,
        "params": {
            "model": "hr.employee",
            "method": "search_read",
            "args": [[["user_id", "=", uid]]],  # Filtro per utente autenticato
            "kwargs": {"fields": ["id", "name"]}  # Restituisci solo ID e Nome
        }
    }

    # Effettuo la richiesta per ottenere il dipendente
    response_employee = session.post(url_employee, json=payload_employee)
    response_employee.raise_for_status()

    # Verifico che ci sia un dipendente associato all'utente
    employees = response_employee.json().get('result', [])
    if not employees:
        raise ValueError("Nessun dipendente trovato per l'utente.")

    #estraggo l'ID del dipendente
    employee_id = employees[0]["id"] 

    # URL per cercare i progetti associati al dipendente
    url_project = f"{odoo_url}/web/dataset/call_kw/account.analytic.line/search_read"
    payload_project = {
    "jsonrpc": "2.0",
    "params": {
        "model": "account.analytic.line",
        "method": "search_read",
        "args": [[]],  # Aggiungi filtri se necessario
        "kwargs": {
            "fields": ["project_id"]  # Ottieni solo il campo project_id
                }
            }
        }

    # Effettuo la richiesta per ottenere i progetti
    response_project = session.post(url_project, json=payload_project)
    response_project.raise_for_status()
    projects = response_project.json().get("result", [])
    project_list = []
    
    # Gestisco i risultati
    if not projects:
        return "Nessun progetto trovato per il dipendente."
    else:
        for project in projects:
            project_list.append(project['project_id'][1])
        project_set = list(set(project_list))
        
    #uso fuzzywuzzy per verificare se il mio progetto esiste e trovare il nome in db
    candidate,score = process.extractOne(project_name,project_set)
    if score > 90:
        return candidate
    else:
        return f'Mi spiace, ma non ho trovato il progetto {project_name}'

#METODO PER TROVARE IL NOME CORRETTO DI UN TASK ASSOCIATO A UN PROGETTO (OK)
def find_task(project_name,task_name):
    #trovo il nome corretto del progetto
    project = find_project(project_name)
    #autenticazione
    _,session = autenticazione()
    #cerco i task associati al progetto
    url_task = f"{odoo_url}/web/dataset/call_kw/project.task/search_read"
    payload_task = {
        "jsonrpc": "2.0",
        "params": {
            "model": "project.task",
            "method": "search_read",
            "args": [[["project_id.name", "=", project]]],  # Filtro per ID del progetto
            "kwargs": {
                "fields": ["name", "stage_id"]  # dettagli del task
            }
        }
    }
    #richiesta api per ottenere i task
    response_task = session.post(url_task, json=payload_task)
    response_task.raise_for_status()
    tasks = response_task.json().get("result", [])
    task_list = []

    # Uso fuzzywuzzy per verificare se il mio task esiste e trovare il nome in db
    if not tasks:
        return f"Nessun task trovato per il progetto '{project_name}'."
    else:
        for task in tasks:
            task_list.append(task['name'])
            
    task_candidate,task_score = process.extractOne(task_name,task_list)
    if task_score > 90:
        return task_candidate
    else:
        return f"Mi spiace, ma non ho trovato il task '{task_name}' nel progetto '{project_name}'."
    

#METODO PER CHECK-IN/CHECK-OUT (OK)
def pausa(input_text):
    template_pausa = PromptTemplate.from_template("""                                          
            Sei un assistente addetto al controllo del check-in o check-out. Riceverai in input una {domanda} dell'utente da cui dovrai capire se vuole effettuare il checkin (inizia a lavorare) o il checkout (smette di lavorare)
                                                  
            ### Struttura dell'output:
            Rispondimi solo con 'check-in' o 'check-out', non voglio nessun'altra parola  

            Esempi:
            Richiesta: "Vado in pausa."
            Output: "check-out"
            
            Richiesta: "Riprendiamo a lavorare"                                          
            Output: "check-in"             

            domanda: {domanda}
    """)
    chain_pausa = template_pausa | llm 
    target_status = chain_pausa.invoke({"domanda": input_text}).content
    
    uid,session = autenticazione()
    
    #determina lo stato corrente
    url_status = f"{odoo_url}/web/dataset/call_kw/hr.attendance/search_read"
    payload_status = {
        "jsonrpc": "2.0",
        "params": {
            "model": "hr.attendance",
            "method": "search_read",
            "args": [[["employee_id.user_id", "=", uid]], ["check_in", "check_out"]],
            "kwargs": {"limit": 1, "order": "check_in desc"},
        },
    }
    response_status = session.post(url_status, json=payload_status)
    response_status.raise_for_status()
    result_status = response_status.json()
    attendance_records = result_status.get("result", []) #stato corrente 
    
    #controllo sullo stato corrente
    if attendance_records:
        last_record = attendance_records[0]
        if last_record["check_out"]:
            current_status = "check-out"
        else:
            current_status = "check-in"
    
    if target_status == current_status:
        return f"Hai già effettuato il {current_status}"
    else:
        url_toggle = f"{odoo_url}/hr_attendance/systray_check_in_out"
        payload_toggle = {
            "jsonrpc": "2.0",
            "params": {},
        }
        response_toggle = session.post(url_toggle, json=payload_toggle)
        response_toggle.raise_for_status()
        result_toggle = response_toggle.json()
        return f"{target_status} effettuato"


def operazione(modello,metodo,dizionario):
    uid,session = autenticazione()
    chiave = 'user_id'
        
    #CASO FERIE
    if modello == 'hr.leave':
        url_employee = f"{odoo_url}/web/dataset/call_kw/hr.employee/search_read"
        # Filtro per cercare il dipendente associato a questo utente
        url_hr = f"{odoo_url}/web/dataset/call_kw/hr.leave.type/web_search_read"
        payload_employee = {
            "jsonrpc": "2.0",
            "params": {
                "model": "hr.employee",
                "method": "search_read",
                "args": [[["user_id", "=", uid]]],  # Filtro per utente
                "kwargs": {"fields": ["id", "name"]}  # Restituisci solo ID e Nome
            }
        }
        
        payload_ferie_id = {
            "jsonrpc": "2.0",
            "params": {
                "model": "hr.leave.type",
                "method": "search_read",
                "args": [[], ["id", "name"]],
                "kwargs": {},
            },
        }
        response_employee = session.post(url_employee, json=payload_employee)
        response_employee.raise_for_status()

        response_ferie_id = session.post(url_hr, json=payload_ferie_id)
        response_ferie_id.raise_for_status()
        types = response_ferie_id.json().get("result", [])
    
        # Verifica che ci sia un dipendente associato all'utente
        try: 
            employees = response_employee.json().get('result', [])
        except Exception as e:
            return "Nessun dipendente trovato per l'utente."
        
        # Ottieni l'ID del dipendente
        uid = employees[0]['id']
        chiave = 'employee_id'
        
    #CASO FOGLIO ORE
    elif modello == 'account.analytic.line':
        # Esempio di ricerca dell'ID di un progetto tramite il nome
        project_name = dizionario['project_id']  # Il nome del progetto che hai
        #print(dizionario['project_id'] )
        # URL per cercare il progetto
        url_project = f"{odoo_url}/web/dataset/call_kw/project.project/search_read"
        payload_project = {
            "jsonrpc": "2.0",
            "params": {
                "model": "project.project",
                "method": "search_read",
                "args": [[["name", "=", project_name]]],  # Filtro per nome del progetto
                "kwargs": {"fields": ["id"]}  # Restituisci solo l'ID
            }
        }

        response_project = session.post(url_project, json=payload_project)
        response_project.raise_for_status()
        projects = response_project.json().get("result", [])

        # Verifica che il progetto esista e ottieni l'ID
        try:
            if projects:
                project_id = projects[0]['id']
            else:
                raise ValueError(f"Progetto '{project_name}' non trovato.")
        except Exception as e:
            return 'Progetto non trovato'
        
        dizionario['project_id'] = project_id
        #caso del task
        if "task_id" in dizionario:
            task_name = dizionario['task_id']
            url_task = f"{odoo_url}/web/dataset/call_kw/project.task/search_read"
            payload_task = {
                "jsonrpc": "2.0",
                "params": {
                    "model": "project.task",
                    "method": "search_read",
                    "args": [[
                        ["name", "=", task_name],  # Filtro per nome del task
                        ["project_id", "=", project_id]  # Filtro per il progetto (opzionale ma utile)
                    ]],
                    "kwargs": {"fields": ["id"]}  # Restituisci solo l'ID
                }
            }

            response_task = session.post(url_task, json=payload_task)
            response_task.raise_for_status()
            tasks = response_task.json().get("result", [])
            try:
                if tasks:
                    task_id = tasks[0]['id']
                else:
                    raise ValueError(f"Task '{task_name}' non trovato nel progetto con ID {project_id}.")
            except Exception as e:
                return 'Task non trovato'
            dizionario['task_id'] = task_id
    
        url_employee = f"{odoo_url}/web/dataset/call_kw/hr.employee/search_read"
        # Filtro per cercare il dipendente associato a questo utente
        payload_employee = {
            "jsonrpc": "2.0",
            "params": {
                "model": "hr.employee",
                "method": "search_read",
                "args": [[["user_id", "=", uid]]],  # Filtro per utente
                "kwargs": {"fields": ["id", "name"]}  # Restituisci solo ID e Nome
            }
        }
        response_employee = session.post(url_employee, json=payload_employee)
        response_employee.raise_for_status()
        employees = response_employee.json().get('result', [])
        uid = employees[0]['id']
        chiave = 'employee_id'
    
    elif modello == 'account.move':
            return 'Operazione fallita'
    
    url = f"{odoo_url}/web/dataset/call_kw/{modello}/{metodo}"
    dizionario[chiave] = uid
    payload = {
        "jsonrpc": "2.0",
        "params": {
            "model": modello,
            "method": metodo,
            "args": [dizionario],
            "kwargs": {}
        }
    }
    # Effettua la richiesta
    try:
        response = session.post(url, json=payload)
        response.raise_for_status()

        # Risultato della richiesta
        result = response.json()
        return 'Operazione eseguita con successo'
        
    except Exception as e:
        return f'Operazione fallita: {e}'

#OPERAZIONI DI CREAZIONE SU ODOO (OK)
def operazione_ERP(input_text):
    """
    Funzione che gestisce le operazioni ERP basate sul testo in input.
    """
    # Template per il prompt
    template_erp = """
        Sei un assistente esperto nella gestione di dati per un sistema ERP. Il tuo compito è generare una richiesta strutturata per eseguire un'operazione su un database Odoo. 
        Rispondi alla {domanda} dell'utente esclusivamente con un JSON che includa:
        1. **Modello** su cui operare (es. "calendar.event").
        2. **Metodo** da eseguire (es. "create").
        3. Un dizionario con i parametri dell'operazione, come specificato.
        
        Regole importanti:
        - Se l'utente ti chiede un'operazione di scrittura (metodo 'create') in una data **minore di {data_oggi}**, non devi eseguire l'operazione.
            In questo caso, rispondi semplicemente con il testo **"Non posso modificare il passato"**.
        - Se la data è corretta o valida (>= {data_oggi}), genera il JSON richiesto.
        - Se l'utente ti chiede di richiedere delle ferie sfrutta il dizionario {id_ferie} per trovare l'id della tipologia di ferie (holiday_status_id)
        
        Esempio:
            Richiesta: chiedi ferie per lutto
            la tipologia di ferie sarà Permesso per Lutto con id 15
            
            Richiesta: chiedi ferie per malattia
            la tipologia di ferie sarà Malattia con id 2
        
        Esempi:

        Richiesta: "Richiedi un giorno di ferie il 7 gennaio."
        Output:
        {{
            "modello": "hr.leave",
            "metodo": "create",
            "dizionario": {{
                "name": "Richiesta ferie",
                "request_date_from": "2024-01-07 00:00:00",
                "request_date_to": "2024-01-07 23:59:59",
                "holiday_status_id": 1,
            }}
        }}

        Richiesta: "Crea una fattura per il cliente nome_cliente con data 7 gennaio 2025"
        Output:
        {{
            "modello": "account.move",
            "metodo": "create",
            "dizionario": {{
                "move_type": "out_invoice",  
                "date": "2025-01-07",         
                "partner_name": "nome_cliente",            
                "invoice_line_ids": [
                    {{
                        "product_id": 1,  // ID del prodotto (modifica se necessario)
                        "quantity": 2,       
                        "price_unit": 100,   
                        "name": "Prodotto XYZ"  
                    }}
                ],
                "journal_id": 1,             
                "payment_reference": "FATTURA-001"  
            }}
        }}

        Richiesta: "Programma un meeting con il team marketing il 15 dicembre dalle 14:00 alle 15:30."
        Output:
        {{
            "modello": "calendar.event",
            "metodo": "create",
            "dizionario": {{
                "name": "Meeting con il team marketing",
                "start": "2024-12-15 14:00:00",
                "stop": "2024-12-15 15:30:00",
                "description": "Discussione sulle strategie di marketing",
                "allday": false
            }}
        }}
        
        Richiesta: "aggiungi un'ora al progetto X il 15 dicembre"
        Output:
        {{
            "modello": "account.analytic.line",
            "metodo": "create",
            "dizionario": {{
                "unit_amount": 1.0,      
                "date": "2024-12-15",
                "project_id": 'X',
            }}
        }}
        
        Richiesta: "aggiungi un'ora al task Y del progetto X il 15 dicembre"
        Output:
        {{
            "modello": "account.analytic.line",
            "metodo": "create",
            "dizionario": {{
                "unit_amount": 1.0,      
                "date": "2024-12-15",
                "project_id": 'X',
                "task_id":Y
            }}
        }}
        
        NOTA BENE: nell'output non inserire mai una coppia chiave-valore relativa all'utente (uid o employee_id)
        
        NOTA BENE: se nell'input non vedi una data specifica, usa questa data corrente: {data_oggi}

        Ora genera il JSON per questa richiesta:
        domanda: {domanda}
        data_oggi: {data_oggi}
        id_ferie: {id_ferie}  
    """
    
    # Preparazione del parser e del prompt
    parser = JsonOutputParser()
    prompt_erp = PromptTemplate(
        template=template_erp,
        input_variables=['domanda', 'data_oggi', 'id_ferie']
    )
    
    # Data corrente formattata
    formatted_time = datetime.now().strftime("%Y-%m-%d")
    
    # Creazione della chain
    chain_erp = prompt_erp | llm | parser
    
    try:
        # Esecuzione della chain
        risposta = chain_erp.invoke({
            "domanda": input_text,
            "data_oggi": formatted_time,
            "id_ferie": id_ferie
        })
        
        # Esecuzione dell'azione
        modello = risposta['modello']
        metodo = risposta['metodo']
        dizionario = risposta['dizionario']
        if 'project_id' in dizionario:
            dizionario['project_id'] = find_project(dizionario['project_id'])
        if 'task_id' in dizionario:
            dizionario['task_id'] = find_task(dizionario['project_id'],dizionario['task_id'])

        result = operazione(modello, metodo, dizionario)
        return result
        
    except Exception as e:
        return f"Errore nell'esecuzione dell'operazione: {str(e)}"
    
#print(operazione_ERP("aggiungi un'ora al foglio ore di oggi al progetto AGILE - JAVA"))

def delete_record(modello,filtri):
    uid,session = autenticazione()
    # Ricerca degli ID dei record da eliminare
    url_search = f"{odoo_url}/web/dataset/call_kw/{modello}/search_read"
    filtri.append(["user_id", "=", uid])
    payload_search = {
        "jsonrpc": "2.0",
        "params": {
            "model": modello,
            "method": "search_read",
            "args": [filtri],
            "kwargs": {
                "fields": ["id","name"],  # Restituisci solo l'ID
                "limit": 0           # Restituisci tutti i risultati corrispondenti
            }
        }
    }
    try:
        response_search = session.post(url_search, json=payload_search)
        response_search.raise_for_status()
        results = response_search.json().get('result', [])
        record_ids = [record['id'] for record in results]
        #print(record_ids)
        #record_ids = [{'id': record['id'], 'name': record['name']} for record in results]
    
    except Exception as e:
        return f"Errore durante la ricerca degli ID: {e}"
        #provo cancellazione
    try:
        # Effettua la richiesta per eliminare il record
        url = f"{odoo_url}/web/dataset/call_kw/{modello}/unlink"
        payload = {
            "jsonrpc": "2.0",
            "params": {
                "model": modello,
                "method": "unlink",
                "args": [record_ids],
                "kwargs": {}
            }
        }
        response = session.post(url, json=payload)
        response.raise_for_status()
        result = response.json()
        #print(result)
        return 'Record eliminato con successo'
    
    except Exception as e:
        return f"Errore durante la cancellazione del record: {e}"
    
#METODO PER ELIMINARE RECORD SU DB ODOO
def eliminazione_ERP(input_text):
    template_eliminazione = PromptTemplate.from_template(
    """ 
        Sei un assistente addetto alla cancellazione di record su Odoo. Analizza la {domanda} dell'utente e capisci i record che vuole eliminare
        
        In output genera un dizionario contente i parametri necessari a trovare l'id del record da eliminare:
        1. Il modello Odoo
        2: i filtri (la chiave deve chiamarsi 'filtri' e deve rispettare la sintassi di ODOO) con cui filtrare lo specifico record da eliminare (non devono mai riguardare user_id o employee_id)
        3: i campi, i campi necessarie per fornire i dati richiesti dall'utente. Nella costruzione dei campi rispondi esclusivamente alla {domanda}, non inserire campi non pertinenti. se per esempio viene richiesto solo un nome o una data, non inserire altro
        
        NOTA BENE: sii preciso nella costruzione dei filtri e sta attento ad adottare la sintassi di ODOO per poter eseguire la query
        NOTA BENE:
        - I filtri possono essere più di uno e devono essere inclusi in un array.
        - L'output deve essere **unicamente** un JSON valido senza alcun testo aggiuntivo.
        - NON usare apostrofi ('), usa sempre le virgolette doppie (").

        ESEMPI:
        Richiesta: "Elimina il meeting del team vendite del 2 dicembre."
        Output:
        {{
            "modello": "calendar.event",
            "filtri": [
                ["name", "=", "Meeting del team vendite"],
                ["start", ">=", "2024-12-02 00:00:00"],
                ["stop", "<=", "2024-12-02 23:59:59"]
            ]
        }}
        
        Richiesta: "Cancella la richiesta di ferie del 7 gennaio."
        Output:
        {{
            "modello": "hr.leave",
            "filtri": [
                ["request_date_from", "=", "2024-01-07"],
                ["holiday_status_id", "=", 1],
            ]
        }}
        
        Richiesta: "Cancella la richiesta di ferie che sono state rifiutate"
        Output:
        {{
            "modello": "hr.leave",
            "filtri": [
                [('state', '=', 'refuse')]
            ]
        }}
        
        Richiesta: "Rimuovi l'evento chiamato 'Riassunto progetto X' del 10 gennaio 2024."
        Output:
        {{
            "modello": "calendar.event",
            "filtri": [
                ["name", "=", "Riassunto progetto X"],
                ["start", ">=", "2024-01-10 00:00:00"],
                ["stop", "<=", "2024-01-10 23:59:59"]
            ]
        }}
        
        Richiesta: "Elimina il foglio ore per il progetto Y del 15 dicembre."
        Output:
        {{
            "modello": "account.analytic.line",
            "filtri": [
                ["project_id.name", "=", "Progetto Y"],
                ["date", "=", "2024-12-15"]
            ]
        }}


        Richiesta: "Cancella la richiesta di congedo parentale per il 20 febbraio."
        Output:
        {{
            "modello": "hr.leave",
            "filtri": [
                ["holiday_status_id", "=", 7], 
                ["request_date_from", "=", "2024-02-20"]
            ]
        }}
        
        IMPORTANTE STRUTTURA OUTPUT: **l'output dovrà essere costituito unicamente dal dizionario, NON DEVI aggiungere altro testo**
        
        NOTA BENE: se nell'input non vedi una data specifica, usa questa data corrente: {data_oggi}. Sfrutta {data_oggi} per avere un contesto temporale

        domanda:{domanda}
        data_oggi:{data_oggi}
    """)
    parser = JsonOutputParser()
    chain_delete = template_eliminazione | llm | parser
    dict = chain_delete.invoke({'domanda':input_text,'data_oggi':formatted_time}) 
    delete_record(dict['modello'],dict['filtri'])
    return dict


def modify_record(modello, filtri,dizionario):
    uid, session = autenticazione()
    
    # Ricerca degli ID dei record
    url_search = f"{odoo_url}/web/dataset/call_kw/{modello}/search_read"
    
    # Aggiungi user_id ai filtri, se necessario
    filtri.append(["user_id", "=", uid])
    
    payload_search = {
        "jsonrpc": "2.0",
        "params": {
            "model": modello,
            "method": "search_read",
            "args": [filtri],
            "kwargs": {
                "fields": ["id"],
                "limit": 1  # Restituisce almeno un record
            }
        }
    }
    
    try:
        response_search = session.post(url_search, json=payload_search)
        response_search.raise_for_status()
        results = response_search.json().get('result', [])
        
        # Verifica se ci sono risultati
        if results:
            record_ids = [record['id'] for record in results]
            print(record_ids)
        else:
            return "Nessun record trovato con i filtri forniti"

    except Exception as e:
        return f"Errore durante la ricerca degli ID: {e}"
    
    url = f"{odoo_url}/web/dataset/call_kw/{modello}/write"
    payload = {
        "jsonrpc": "2.0",
        "params": {
            "model": modello,
            "method": "write",
            "args": [record_ids],
            "kwargs": dizionario
        }
    }
    try:
        response = session.post(url, json=payload)
        response.raise_for_status()
        result = response.json()

        if result.get("error"):
            return f"Errore durante la modifica del record: {result['error']}"
        else:
            return "Operazione riuscita!"
        
    except Exception as e:
        return f"Errore durante la modifica del record: {e}"
   
def modifica_ERP(input_text):
    """
    Funzione che gestisce le operazioni ERP basate sul testo in input.
    """
    # Template per il prompt
    template_modifica = PromptTemplate.from_template(
    """ 
        Sei un assistente addetto alla modifica di record su Odoo. Analizza la {domanda} dell'utente e capisci i record che vuole eliminare
        
        In output genera un dizionario contente i parametri necessari a trovare l'id del record da modificare e a registrare il nuovo record:
        1. Il modello Odoo
        2: i filtri (la chiave deve chiamarsi 'filtri' e deve rispettare la sintassi di ODOO) con cui filtrare lo specifico record da eliminare (non devono mai riguardare user_id o employee_id)
        3: i campi, i campi necessarie per fornire i dati richiesti dall'utente. Nella costruzione dei campi rispondi esclusivamente alla {domanda}, non inserire campi non pertinenti. se per esempio viene richiesto solo un nome o una data, non inserire altro
        
        NOTA BENE: sii preciso nella costruzione dei filtri e sta attento ad adottare la sintassi di ODOO per poter eseguire la query
        NOTA BENE:
        - I filtri possono essere più di uno e devono essere inclusi in un array.
        - L'output deve essere **unicamente** un JSON valido senza alcun testo aggiuntivo.
        - NON usare apostrofi ('), usa sempre le virgolette doppie (").

        ESEMPI:
        Richiesta: "sposta il meeting col team vendite del 15 dicembre al 18 dicembre dalle 14 alle 15:30"
        Output:
        {{
            "modello": "calendar.event",
            "metodo": "write",
            "filtri": [
                ["start", ">=", "2024-12-02 00:00:00"],
                ["stop", "<=", "2024-12-02 23:59:59"]
            ],
            "dizionario": {{
                "start_datetime": "2024-12-18 14:00:00",
                "stop_datetime": "2024-12-18 15:30:00",
            }}
        }}
        
        Richiesta: "Sposta la richiesta di ferie del 7 gennaio al 9 gennaio."
        Output:
        {{
            "modello": "hr.leave",
            "metodo": "write",
            "filtri": [
                ["request_date_from", "=", "2024-01-07"],
                ["holiday_status_id", "=", 1],
            ],
            "dizionario": {{
                "request_date_from": "2024-01-09 00:00:00",
                "request_date_to": "2024-01-09 23:59:59",
            }}
        }}
        
      
        Richiesta: "il numero di ore di oggi sul progetto X è pari a 2"
        Output:
        {{
            "modello": "account.analytic.line",
            "metodo": "write",
            "filtri": [
                ["project_id.name", "=", "Progetto X"],
                ["date", "=", "2024-12-15"]
            ],
            "dizionario": {{
                "unit_amount": 2.0,      
                "date": "2024-12-15",
                "project_id": 'X',
                "task_id":Y
            }}
        }}
        
        IMPORTANTE STRUTTURA OUTPUT: **l'output dovrà essere costituito unicamente dal dizionario, NON DEVI aggiungere altro testo**
        
        NOTA BENE: se nell'input non vedi una data specifica, usa questa data corrente: {data_oggi}. Sfrutta {data_oggi} per avere un contesto temporale

        domanda:{domanda}
        data_oggi:{data_oggi}
    """)
    
    
    # Data corrente formattata
    formatted_time = datetime.now().strftime("%Y-%m-%d")
    parser = JsonOutputParser()
    chain_modify = template_modifica | llm | parser
    dict = chain_modify.invoke({'domanda':input_text,'data_oggi':formatted_time}) 
    result = modify_record(dict['modello'],dict['filtri'],dict['dizionario'])
    return result

print(modifica_ERP("sposta le ferie di domani al 13 gennaio"))


#print(operazione_ERP("elimina un'ora al foglio ore di oggi al progetto odoo chatbot"))
#print(eliminazione_ERP("elimina le ferie di domani"))    
#print(eliminazione_ERP("elimina il foglio ore di oggi al progetto ODOO CHATBOT"))
#print(invio_mail("andrea pastore","ciao","FNS"))
#print(operazione_ERP("crea un evento in calendario per domani con nome prova"))

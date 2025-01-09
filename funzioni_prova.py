    # # Invia la campagna email (o la mette in coda per l'invio)
    # url_send_mail = f"{odoo_url}/web/dataset/call_kw/mail.mass_mailing.action_send"
    # payload_send_mail = {
    #     "jsonrpc": "2.0",
    #     "params": {
    #         "model": "mail.mass_mailing",
    #         "method": "send_mass_mailing",
    #         "args": [mailing_id],
    #         "kwargs": {}
    #     }
    # }

    # try:
    #     response_send_mail = session.post(url_send_mail, json=payload_send_mail)
    #     response_send_mail.raise_for_status()
    #     return f"Email inviata con successo a {partner_mail}"
    # except requests.exceptions.RequestException as e:
    #     print(f"Errore nell'invio della campagna: {str(e)}")
    #     return None
    #return mailing_id,session.post(url_mailing, json=payload_create_mailing)
    
#print(send_mail('andrea pastore','ciao','come stai'))

def invio_mail(partner_name, subject, body_html):
    """
    Cerca il contatto (res.partner) in modo fuzzy su Odoo,
    poi invia una mail utilizzando il modello "mail.mail".
    :param partner_name: Nome (o porzione di nome) del contatto da cercare.
    :param subject: Oggetto dell'email.
    :param body_html: Corpo dell'email in formato HTML.
    :return: Messaggio di successo o errore.
    """
    # 1 Autenticazione e creazione sessione
    uid, session = autenticazione()  # Supponendo che tu abbia già definito questa funzione
    
    if not uid or not session:
        return "Autenticazione fallita!"
    
    # 2 Ricerca di tutti i partner
    
    url_search_partner = f"{odoo_url}/web/dataset/call_kw/res.partner/search_read"
    payload_partner = {
        "jsonrpc": "2.0",
        "params": {
            "model": "res.partner",
            "method": "search_read",
            "args": [[]],  # Nessun filtro: scarico tutti i partner (in casi reali meglio filtrare)
            "kwargs": {
                "fields": ["id", "name", "email"]
            }
        }
    }
    try:
        response_partner = session.post(url_search_partner, json=payload_partner)
        response_partner.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"Errore nella chiamata search_read: {str(e)}"
    partners = response_partner.json().get("result", [])
    if not partners:
        return "Nessun partner trovato."
    # 3 Uso di fuzzywuzzy per trovare il partner con nome più simile
    partner_names = [p["name"] for p in partners]
    best_match, score = process.extractOne(partner_name, partner_names)
    if score < 80:  # soglia di similarità (regolabile)
        return f"Non ho trovato contatti con un nome simile a '{partner_name}'."
    
    # 4 Recupero i dati del partner effettivo
    found_partner = next(p for p in partners if p["name"] == best_match)
    partner_id = found_partner["id"]
    partner_email = found_partner["email"]
    if not partner_email:
        return f"Il partner '{best_match}' non ha un indirizzo email definito."
    
    # 5 Creazione della mail (mail.mail) via API Odoo
    url_create_mail = f"{odoo_url}/web/dataset/call_kw/mail.mail/create"
    mail_values = {
        "subject": subject,
        "body_html": body_html,
        "email_to": partner_email,
        "email_from": username,
        "type": "email",
        # In molti casi è bene impostare anche "email_from" (o verrà usato quello di default)
    }
    payload_create_mail = {
        "jsonrpc": "2.0",
        "params": {
            "model": "mail.mail",
            "method": "create",
            "args": [mail_values],
            "kwargs": {}
        }
    }
    try:
        response_create = session.post(url_create_mail, json=payload_create_mail)
        response_create.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"Errore nella creazione del record mail.mail: {str(e)}"
    created_mail_id = response_create.json().get("result")
    return created_mail_id,response_create.json()
    if not created_mail_id:
        return f"Impossibile creare il record mail.mail per il partner '{best_match}'."
    # 6 Invio della mail (forzato) via API Odoo
    url_send_mail = f"{odoo_url}/web/dataset/call_kw/mail.mail/send"
    payload_send_mail = {
        "jsonrpc": "2.0",
        "params": {
            "model": "mail.mail",
            "method": "send",
            "args": [[created_mail_id]],
            "kwargs": {}
        }
    }
    try:
        response_send = session.post(url_send_mail, json=payload_send_mail)
        response_send.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"Errore nell'invio della mail: {str(e)}"
    # Se va tutto bene
    return f"Email inviata correttamente a '{best_match}' (score fuzzy: {score})."


def send_mail(partner_name,subject,body):
    """
    Invia un'email a un partner utilizzando il modulo Marketing via Email.
    
    :param partner_name: Nome (o porzione di nome) del contatto da cercare.
    :param subject: Oggetto dell'email.
    :param body: Corpo dell'email in formato HTML.
    """

    #autenticazione
    uid,session = autenticazione()
    if not uid or not session:
        return "autenticazione fallita"

    #ricerca del partner
    url_partner = f"{odoo_url}/web/dataset/call_kw/res.partner/search_read"
    payload_partner = {
        "jsonrpc": "2.0",
        "params": {
            "model": "res.partner",
            "method": "search_read",
            "args": [[]],  
            "kwargs": {
                "fields": ["id", "name", "email"]
            }
        }
    }
    try:
        response_partner = session.post(url_partner,json=payload_partner)
        response_partner.raise_for_status()
        partners = response_partner.json().get("result",[])
        if not partners:
            return "partner non trovato"
        partner_names = [p['name'] for p in partners]
        best_match,score = process.extractOne(partner_name,partner_names)
        if score < 80:
            return "partner non trovato"
        else: 
            partner = next(p for p in partners if p["name"] == best_match)

    except requests.exceptions.RequestException as e:
        print(f"Errore nella chiamata search_read: {str(e)}")
        return None
    partner_mail = partner.get("email")

    #creo mailing
    url_mailing = f"{odoo_url}/web/dataset/call_kw/mail.mass_mailing.create"
    mailing_values = {
        "subject": subject,
        "body_html": body,
        "email_from": username,
        "email_to": partner_mail,
        "state": "draft",  # In stato di bozza
    }
    payload_create_mailing = {
        "jsonrpc": "2.0",
        "params": {
            "model": "mail.mass_mailing",
            "method": "create",
            "args": [mailing_values],
            "kwargs": {}
        }
    }

    try:
        response_create_mailing = session.post(url_mailing, json=payload_create_mailing)
        response_create_mailing.raise_for_status()
        mailing_id = response_create_mailing.json().get("result")
        return mailing_id,session.post(url_mailing, json=payload_create_mailing).json()
    except requests.exceptions.RequestException as e:
        print(f"Errore nella creazione del mailing: {str(e)}")
        return None
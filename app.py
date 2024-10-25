from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import ibm_boto3
from ibm_botocore.client import Config, ClientError
import json

app = Flask(__name__)
CORS(app)

# IBM Cloud Object Storage konfigurálása
cos = ibm_boto3.client(
    's3',
    ibm_api_key_id='UZ0-SGtOYDF0aGrbKO9fAvBwy901L0xZqd7dJfWveV-2',
    ibm_service_instance_id='crn:v1:bluemix:public:cloud-object-storage:global:a/c9b79e3ae1594628bb4d214193b9cb75:e310fa1f-ff9f-443e-b3fd-c86719b7e9e6:bucket:elekteszt',
    config=Config(signature_version='oauth'),
    endpoint_url='https://s3.us-south.cloud-object-storage.appdomain.cloud'
)

# DROPDOWN_OPTIONS dinamikus feltöltése COS-ból
DROPDOWN_OPTIONS = {
    "assignment_groups": {"values": [], "labels": []},
    "priorities": {"values": [], "labels": []}
}

# Segédfüggvény a dropdown opciók lekérésére és feltöltésére
def load_dropdown_options():
    try:
        # Assignment groups lekérése
        response = cos.get_object(Bucket='elekteszt', Key='admin_assignment_groups')
        assignment_groups = json.loads(response['Body'].read().decode('utf-8'))
        DROPDOWN_OPTIONS["assignment_groups"]["values"] = [item["sys_id"] for item in assignment_groups]
        DROPDOWN_OPTIONS["assignment_groups"]["labels"] = [item["name"] for item in assignment_groups]

        # Priorities lekérése
        response = cos.get_object(Bucket='elekteszt', Key='admin_priorities')
        priorities = json.loads(response['Body'].read().decode('utf-8'))
        DROPDOWN_OPTIONS["priorities"]["values"] = [item["value"] for item in priorities]
        DROPDOWN_OPTIONS["priorities"]["labels"] = [item["label"] for item in priorities]

        print("DROPDOWN_OPTIONS sikeresen betöltve a COS-ból.")
    except ClientError as e:
        print(f"Error loading dropdown options: {e}")

# 1. Bejelentkezési és COS-ba mentési szakasz
@app.route('/login', methods=['POST'])
def login_and_store_data():
    request_data = request.json
    username = request_data.get('username')
    password = request_data.get('password')

    # Bejelentkezéshez token megszerzése
    auth_data = {
        'grant_type': 'password',
        'client_id': '45f3f2fb2ead4928ab994c64c664dfdc',
        'client_secret': 'fyHL1.@d&7',
        'username': username,
        'password': password
    }

    # Token lekérése a ServiceNow-tól
    response = requests.post('https://dev227667.service-now.com/oauth_token.do', data=auth_data)
    if response.status_code == 200:
        access_token = response.json().get('access_token')

        # Token tárolása a COS-ban
        cos.put_object(Bucket='elekteszt', Key='admin_token', Body=access_token)

        # Felhasználói sys_id lekérése
        headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
        response_user = requests.get(
            f"https://dev227667.service-now.com/api/now/table/sys_user?sysparm_query=user_name={username}",
            headers=headers
        )
        if response_user.status_code == 200:
            caller_id = response_user.json().get('result', [])[0].get("sys_id")
            cos.put_object(Bucket='elekteszt', Key='admin_caller_id', Body=caller_id)

            # Dropdown opciók betöltése COS-ból
            load_dropdown_options()

            return jsonify({"message": "Bejelentkezés sikeres, adatok tárolva."}), 200
        else:
            return jsonify({"error": "Felhasználói azonosító lekérése sikertelen."}), 400
    else:
        return jsonify({"error": "Authentication failed", "details": response.text}), 400

# 2. Jegy létrehozása kiválasztott dropdown opciókkal
@app.route('/create_ticket', methods=['POST'])
def create_ticket():
    request_data = request.json

    # Token és caller_id betöltése COS-ból
    response_token = cos.get_object(Bucket='elekteszt', Key='admin_token')
    access_token = response_token['Body'].read().decode('utf-8')

    response_caller = cos.get_object(Bucket='elekteszt', Key='admin_caller_id')
    caller_id = response_caller['Body'].read().decode('utf-8')

    short_description = request_data.get('short_description')
    assignment_group_name = request_data.get('assignment_group_name')
    priority_label = request_data.get('priority_label')

    # A kiválasztott nevek alapján megtaláljuk a megfelelő sys_id-t és value-t
    try:
        assignment_group_sys_id = DROPDOWN_OPTIONS["assignment_groups"]["values"][
            DROPDOWN_OPTIONS["assignment_groups"]["labels"].index(assignment_group_name)
        ]
        priority_value = DROPDOWN_OPTIONS["priorities"]["values"][
            DROPDOWN_OPTIONS["priorities"]["labels"].index(priority_label)
        ]
    except ValueError:
        return jsonify({"error": "Invalid selection for assignment group or priority"}), 400

    # Jegy adatainak felépítése és elküldése
    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
    ticket_data = {
        "short_description": short_description,
        "assignment_group": assignment_group_sys_id,
        "priority": priority_value,
        "caller_id": caller_id
    }

    response_ticket = requests.post('https://dev227667.service-now.com/api/now/table/incident', json=ticket_data, headers=headers)
    if response_ticket.status_code == 201:
        return jsonify({
            "message": "Jegy sikeresen létrehozva",
            "ticket_number": response_ticket.json().get('result', {}).get('number')
        }), 201
    else:
        return jsonify({
            "error": "Jegy létrehozása sikertelen",
            "details": response_ticket.text
        }), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

from flask import Flask, render_template
import plotly.express as px
import plotly.io as pio
from flask import Flask, request, jsonify
import base64
import json
import os
import fastf1 as ff1
import plotly.graph_objects as go
from plotly.subplots import make_subplots

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/generate', methods=['GET'])
def generate():
    base64_json = request.args.get('data')

    # Get the 'data' parameter from the query string
    base64_json = request.args.get('data')

    if not base64_json:
        return jsonify({"error": "No data parameter provided"}), 400

    try:
        # Decode the Base64-encoded string
        decoded_json = base64.b64decode(base64_json).decode('utf-8')

        # Parse the decoded string into a JSON object
        input_data = json.loads(decoded_json)

        year = input_data["year"]
        grand_prix = input_data["grand_prix"]
        drivers = input_data["drivers"]

        # Plotting setup
        col_dict = {
            "PER": "Blue", "VER": "Blue", "LEC": "Red", "SAI": "Red", "RUS": "Cyan",
            "HAM": "Cyan", "ALO": "Green", "STR": "Green", "PIA": "#ff8700", 
            "NOR": "#ff8700", "ALB": "#005aff", "GAS": "#0090ff", "OCO": "#0090ff"
        }

        distance_min, distance_max = 1140, 2400
        turn_nos = {"Turn-1": 1520, "Turn-2": 2000}

        telemetry_colors = {
            'Full Throttle': 'green', 'Turning': 'yellow', 'Brake': 'red'
        }

        # Load the selected session data
        session = ff1.get_session(year, grand_prix, 'RACE')
        session.load(weather=False)

        # Initialize subplots with a 2-row layout and specific height ratios
        fig = make_subplots(rows=2, cols=1, row_heights=[0.75, 0.25], shared_xaxes=True,
                            subplot_titles=["Speed vs Distance", "Driver Actions"])

        # Create first subplot (Speed vs Distance) for each driver
        for dr in drivers:
            laps_driver = session.laps.pick_driver(dr).pick_fastest()
            telemetry_driver = laps_driver.get_car_data().add_distance()

            # Extract telemetry data for each driver
            fig.add_trace(
                go.Scatter(
                    x=telemetry_driver['Distance'], y=telemetry_driver['Speed'],
                    mode='lines', name=dr, line=dict(width=3, color=col_dict[dr])
                ),
                row=1, col=1
            )

            # Add turns as vertical lines
            for g in turn_nos:
                fig.add_vline(x=turn_nos[g], line_width=2, line_dash='dash', line_color='yellow', row=1, col=1)
                fig.add_annotation(x=turn_nos[g], y=0, text=g, showarrow=False, yshift=10,
                                font=dict(size=14, color='black', family="Arial Black"),
                                bgcolor="white", row=1, col=1)

        # Set axis titles and styling for the first subplot (Speed vs Distance)
        fig.update_xaxes(title_text="Distance", row=1, col=1)
        fig.update_yaxes(title_text="Speed", row=1, col=1)

        # Create second subplot (Driver Actions) with horizontal bar chart for each driver
        y_positions = list(range(len(drivers)))
        for i, dr in enumerate(drivers):
            laps_driver = session.laps.pick_driver(dr).pick_fastest()
            telemetry_driver = laps_driver.get_car_data().add_distance()

            # Process driver actions: Brake, Full Throttle, and Turning
            telemetry_driver.loc[telemetry_driver['Brake'] > 0, 'CurrentAction'] = 'Brake'
            telemetry_driver.loc[telemetry_driver['Throttle'] > 96, 'CurrentAction'] = 'Full Throttle'
            telemetry_driver.loc[(telemetry_driver['Brake'] == 0) & (telemetry_driver['Throttle'] < 96), 'CurrentAction'] = 'Turning'

            telemetry_driver['ActionID'] = (telemetry_driver['CurrentAction'] != telemetry_driver['CurrentAction'].shift(1)).cumsum()
            actions_driver = telemetry_driver[['ActionID', 'CurrentAction', 'Distance']].groupby(['ActionID', 'CurrentAction']).max('Distance').reset_index()

            actions_driver['DistanceDelta'] = actions_driver['Distance'] - actions_driver['Distance'].shift(1)
            actions_driver.loc[0, 'DistanceDelta'] = actions_driver.loc[0, 'Distance']

            previous_action_end = 0
            for _, action in actions_driver.iterrows():
                fig.add_trace(
                    go.Bar(
                        x=[action['DistanceDelta']],
                        y=[dr], orientation='h', name=action['CurrentAction'],
                        marker_color=telemetry_colors[action['CurrentAction']],
                        hoverinfo='name',
                        base=previous_action_end,
                        showlegend=(i == 0)  # Show legend only for the first driver
                    ),
                    row=2, col=1
                )
                previous_action_end += action['DistanceDelta']

        # Set styling for the second subplot (Driver Actions)
        fig.update_yaxes(title_text="Driver", row=2, col=1, tickvals=y_positions, ticktext=drivers)
        fig.update_xaxes(title_text="Distance", row=2, col=1)

        # Add a title and adjust the layout
        fig.update_layout(
            title=f"{session.event.year} {session.event['EventName']} (RACE)\n Corner Analysis {drivers[0]} vs {drivers[1]} vs {drivers[2]}",
            height=700, legend_title_text="Telemetry Actions", legend=dict(orientation="h", yanchor="bottom", y=-0.3, x=0),
            template='plotly_dark', margin=dict(l=50, r=50, t=80, b=50)
        )

        fig.update_layout(template='plotly_dark')

        graph_html = pio.to_html(fig, full_html=False)

        return render_template('generate.html', plot=graph_html)

    except (base64.binascii.Error, json.JSONDecodeError) as e:
        return jsonify({"error": str(e)}), 400  

if __name__ == "__main__":
    # Create the cache directory if it doesn't exist
    cache_directory = 'cache/'
    if not os.path.exists(cache_directory):
        os.makedirs(cache_directory)
        
    ff1.Cache.enable_cache('cache/')

    # Load the selected session data
    years = list(range(2020, 2024))
    grand_prixs = ['British Grand Prix', 'Monaco Grand Prix', 'Belgian Grand Prix']

    for year in years:
        for grand_prix in grand_prixs:
            session = ff1.get_session(year, grand_prix, 'RACE')
            session.load(weather=False)

    app.run(debug=True)
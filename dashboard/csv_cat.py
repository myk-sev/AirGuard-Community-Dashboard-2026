import pandas as pd
from pathlib import Path

def concatenate(input: String, output: String) -> void:
    csv_files = []

    new_file: DataFrame = pd.read_csv(input, index_col=False, header=0)
    old_file: DataFrame = pd.read_csv(output, index_col=False, header=0)

    if 'Timestamp for sample frequency every 1 min min' in new_file.columns:
        new_file["Time"] = pd.to_datetime(new_file['Timestamp for sample frequency every 1 min min'])
        new_file.drop(columns=['Timestamp for sample frequency every 1 min min'], inplace=True)

    if 'Time(DD/MM/YYYY h:mm:ss A)' in new_file.columns:
        new_file["Time"] = pd.to_datetime(new_file['Time(DD/MM/YYYY h:mm:ss A)'], format = "%d/%m/%Y %I:%M:%S %p")
        new_file.drop(columns=['Time(DD/MM/YYYY h:mm:ss A)'], inplace=True)

    if 'Sensor name' not in new_file.columns:
        # NOTE: Does not work with Aranet naming scheme
        # NOTE: Govee naming scheme should be: BuildingName-Placement
        name = Path(i).name.split('_')[0]
        new_file.loc[:, "Sensor name"] = name
        new_file.loc[:, "Building"] = name.split('-')[0]
        new_file.loc[:, "Location"]  = name.split('-')[-1]

    csv_files.append(new_file)

    frame = pd.concat(csv_files, axis=0, ignore_index=True)

    frame.drop_duplicates(subset=["Time", "Sensor name"], inplace=True)

    frame.to_csv(output, index=False)


import pandas as pd
from pathlib import Path

def concatenate(input: String, output: String) -> void:
    csv_files = []

    new_file: DataFrame = pd.read_csv(input, index_col=False, header=0)
    old_file: DataFrame = pd.read_csv(output, index_col=False, header=0)

    # TODO: specify pre-conversion time formats
    if 'Timestamp for sample frequency every 1 min min' in new_file.columns:
        new_file["Time"] = pd.to_datetime(new_file['Timestamp for sample frequency every 1 min min'])
        new_file.drop(columns=['Timestamp for sample frequency every 1 min min'], inplace=True)

    if 'Time(DD/MM/YYYY h:mm:ss A)' in new_file.columns:
        new_file["Time"] = pd.to_datetime(new_file['Time(DD/MM/YYYY h:mm:ss A)'])
        new_file.drop(columns=['Time(DD/MM/YYYY h:mm:ss A)'], inplace=True)

    if 'Sensor name' not in new_file.columns:
        new_file.loc[:, "Sensor name"] = Path(i).name.split('.')[0]

    csv_files.append(new_file)

    frame = pd.concat(csv_files, axis=0, ignore_index=True)

    frame.drop_duplicates(subset=["Time", "Sensor name"], inplace=True)

    frame.to_csv(output, index=False)


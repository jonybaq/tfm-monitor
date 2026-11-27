using './main.bicep'

param image = readEnvironmentVariable('BACKEND_IMAGE')
param apiToken = readEnvironmentVariable('CAMERA_CONTROL_API_TOKEN')
param websocketToken = readEnvironmentVariable('CAMERA_CONTROL_WS_TOKEN')

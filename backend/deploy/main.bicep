param location string = 'chilecentral'
param image string
@secure()
param apiToken string
@secure()
param websocketToken string

resource pullIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'id-tfm-backend-pull'
}

resource environment 'Microsoft.App/managedEnvironments@2025-07-01' = {
  name: 'env-tfm-backend'
  location: location
  properties: {
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

resource backend 'Microsoft.App/containerApps@2025-07-01' = {
  name: 'tfm-camera-backend'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${pullIdentity.id}': {}
    }
  }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8080
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: 'tfmtapobackend.azurecr.io'
          identity: pullIdentity.id
        }
      ]
      secrets: [
        {
          name: 'camera-api-token'
          value: apiToken
        }
        {
          name: 'camera-ws-token'
          value: websocketToken
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: image
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'BACKEND_BIND_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'CAMERA_CONTROL_API_TOKEN'
              secretRef: 'camera-api-token'
            }
            {
              name: 'CAMERA_CONTROL_WS_TOKEN'
              secretRef: 'camera-ws-token'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 1
      }
    }
  }
}

output url string = 'https://${backend.properties.configuration.ingress.fqdn}'

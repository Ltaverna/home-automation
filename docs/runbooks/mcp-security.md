# Seguridad del MCP (ha_mcp_tools)

El MCP expone la casa a agentes (Claude/ChatGPT) por internet. Modelo de seguridad en capas.

## Capas de autenticación

1. **Cloudflare Access** (puerta de identidad, delante del túnel) — ver "Cloudflare Access" abajo.
   Login por OTP al email de Lucas; sin identidad válida no se llega al MCP.
2. **secret_path** (2da capa, defensa en profundidad) — la URL del connector incluye un path
   secreto aleatorio que es la credencial del `ha_mcp_tools`. Se mantiene aunque haya Access.
3. **Transporte** — túnel Cloudflare `ha-mcp.neuralcore.dev` → `:9584` (contenedor `cloudflared-mcp`).

## Deny floor del componente (no-anulable)

`ha_mcp_tools` trae un piso de denegación que NINGUNA config de usuario puede levantar
(`custom_components/ha_mcp_tools/const.py`):
- `DENY_PATH_SEGMENTS = {".storage"}` — protege la auth DB de HA (tokens de acceso/refresh,
  passwords hasheadas, el token del propio MCP).
- `DENY_READ_BASENAMES = {"secrets.yaml", "approval_pin.json"}` — `secrets.yaml` solo es
  accesible como archivo canónico con sus valores **enmascarados**; cualquier otro se deniega.

Es un allowlist con piso: aunque se agreguen directorios de lectura/escritura extra, estos
paths quedan bloqueados.

## Exposición a Assist

La exposición nativa a la API de Assist está **prácticamente vacía**
(`.storage/homeassistant.exposed_entities`: solo `conversation.home_assistant`, `zone.home`,
`sun.sun` marcados como NO expuestos; sin default global). El control real del MCP pasa por las
tools extendidas de `ha_mcp_tools` (`llm_api_exposure: both`), acotadas por el deny floor.
Si se quisiera limitar aún más, curar explícitamente qué entidades se exponen a `conversation`.

## No expuesto / fuera de alcance de tools agentic

- **Cerradura Philips DDL615**: autónoma, sin integración en HA por decisión (ver spec). El MCP
  no puede abrir la puerta porque la cerradura no es una entidad de HA. Regla dura: **MCP/LLM ✗ unlock**.
- No hay entidades de alarma/lock integradas hoy; si se agregan, NO exponerlas al MCP.

## Rotación del secret_path

Si el secret_path se filtra: Settings → Integrations → **HA-MCP** → opciones →
`regenerate_secrets`. Genera un nuevo path (aplica en vivo); actualizar la URL en los connectors.

## Cloudflare Access — vía MCP Server Portal (NO Access self-hosted app)

**Decisión de diseño (importante):** NO poner una Access self-hosted app directamente sobre
`ha-mcp.neuralcore.dev`. Los clientes MCP (Claude/ChatGPT) autentican por **OAuth**, no por la
cookie de Access; una self-hosted app rompería el connector. El primitivo correcto es el
**MCP Server Portal** (Zero Trust → Access controls → MCP Portals), que es **aditivo**: crea un
subdominio nuevo (`https://<sub>.neuralcore.dev/mcp`) y deja el endpoint actual intacto. Los
clientes no-browser reciben `401` + discovery OAuth en `WWW-Authenticate` y completan el flujo
contra Cloudflare Access (login OTP de Lucas).

- Cuenta: `115a2f9419ee3033fde16851a506c0d6` · Zona `neuralcore.dev` · Team `neuralcore.cloudflareaccess.com`.

### Pasos (dashboard — vía soportada)
1. Zero Trust → Access controls → **MCP servers** → *Add an MCP server*: nombre `ha-mcp`,
   HTTP URL = `https://ha-mcp.neuralcore.dev/<secret_path>` (el path del connector actual),
   auth type **unauthenticated** (el secret_path ya es la credencial del upstream).
2. Access controls → **MCP Portals** → *Add MCP server portal*: nombre, subdominio en
   `neuralcore.dev`, agregar el server `ha-mcp`, **Require user auth**.
3. Adjuntar una **Access policy**: allow por email `lucas@bold-agro.ai` (login OTP).
4. En los connectors de ChatGPT/Claude, cambiar la URL a `https://<sub>.neuralcore.dev/mcp`.

### API (verificado) y estado actual
Endpoints reales: `POST /accounts/<acc>/access/ai-controls/mcp/{servers,portals}`. Requieren en el
API token el permission group **"MCP Portals"** (no "AI Controls") además de Access: Apps and
Policies — sin él dan 403. Schema descubierto por prueba (beta, sin doc pública):
- **server**: `{id, name, hostname (URL completa), auth_type: oauth|bearer|unauthenticated}`
- **portal**: `{id, name, hostname, servers:[{server_id, require_user_auth?}]}`

**Ya creado por API (2026-09-28):**
- MCP server `ha-mcp` → upstream `https://ha-mcp.neuralcore.dev<secret_path>`, auth `unauthenticated`
  (el secret_path es la credencial). Las tools de HA **sincronizaron OK** (el portal alcanza el MCP).
- Portal `ha-portal` (hostname `ha-portal.neuralcore.dev`) con el server adjunto, status `ready`.

**Falta (mejor por dashboard, que cablea DNS + Access app + policy automáticamente):**
1. Enrutar el hostname del portal (DNS) — el token no tiene DNS:Read/Edit y los hostnames de túnel
   se manejan por cloudflared; el dashboard lo resuelve.
2. Habilitar **Require user auth** + adjuntar Access policy (allow `lucas@bold-agro.ai`, login OTP).
   La identidad del portal se enforcea con la Access application asociada (no hay campo de policy en
   el objeto portal por API).
3. En ChatGPT/Claude apuntar el connector a `https://ha-portal.neuralcore.dev/mcp` y testear.

Hasta que exista el DNS, `ha-portal.neuralcore.dev` **no resuelve** → no hay endpoint expuesto.

> **Rotar el secret_path**: durante el armado por API el secret_path apareció en un output. Rotarlo
> con `regenerate_secrets` (options flow) invalida el valor viejo; después actualizar el `hostname`
> del server `ha-mcp` en el portal con la URL nueva.

- **Rollback**: borrar el portal/servidor en el dashboard → el MCP sigue accesible por el
  endpoint actual (secret_path). El endpoint viejo nunca se toca, así que no hay pérdida de acceso.

## Norte (futuro)

Migrar de secret_path a **OAuth puro** (`ha_auth`) una vez validado Access con los connectors, y
recién ahí evaluar sacar el secret_path. Mientras tanto, Access + secret_path es defensa en profundidad.

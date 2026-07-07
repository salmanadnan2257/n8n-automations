# Credentials

External services and credentials these three workflows' nodes require to run:

- **Cal.com API (v2)**: used by the active availability and booking calls in all
  three workflows: `Get Available Times - Cal.com` (GET `/v2/slots`) in
  get-available-times.json and specific-available-booking-times.json, and
  `Book Time` (POST `/v2/bookings`) in book-available-time.json. Referenced in the
  JSON as an n8n `calApi` credential pointer.
- **Cal.com API (v2), HTTP header variant**: the disabled `Reserve Time` node in
  book-available-time.json (POST `/v2/slots/reservations`) additionally references
  a generic `httpHeaderAuth` credential pointer alongside `calApi`. This node is
  disabled and disconnected in the active graph, so it is not required to run the
  workflow as shipped, only if the reserve-then-book path is reactivated.
- **Calendly API**: referenced by `user_uri`, `event_uri`, and
  `Get Available Times - Calendly` in all three workflows (an `calendlyApi`
  credential pointer). Every one of these nodes is disabled; Calendly was an
  intended availability/booking source that never went live, so this credential is
  not needed to run the current active paths, only if Calendly support is finished
  and re-enabled.
- **n8n Webhook (built-in, no external account)**: each workflow's entry point is a
  `n8n-nodes-base.webhook` node listening for a POST request. No credential is
  needed for this, but the calling system needs the workflow's webhook URL and must
  send the expected JSON body fields (see README.md Usage section for each
  workflow's expected fields).

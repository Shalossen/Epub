# Mobile App (Epub Reader)

- Install: `npm install`
- Run server: `cd ../server && npm run start`
- Set API URL for mobile (optional): create `.env` in `mobile` with `EXPO_PUBLIC_API_URL=http://127.0.0.1:8080`
- Start mobile: `npm run web` or `npm run android`

Features:
- Import `.epub` files, read with adjustable font size, theme, paragraph alignment, and flow (paginated/scroll)
- AI menu (screen) to upload book to backend, run analysis (characters, keywords, complexity)
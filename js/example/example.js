const open = require('open');
const express = require('express')
const path = require('path');
const {generateQRCode, generateQRData} = require('../src')
const QRCode = require("qrcode");
const {
    DEFAULT_QR_QUALITY,
    DEFAULT_QR_BORDER,
    DEFAULT_QR_SCALE,
    COLOR_BLACK,
    COLOR_WHITE, DEFAULT_ECC_LEVEL
} = require("../src/shared/Constants");

const app = express()
const port = 3000

app.use(express.text())
app.get('/', (req, res) => {
    const options = {
        root: path.join(__dirname)
    };
    res.sendFile("index.html", options)
})

app.get('/styles.css', (req, res) => {
    const options = {
        root: path.join(__dirname)
    };
    res.sendFile("stylesheet.css", options)
})

app.post('/qr', (req, res) => {
    let json = req.body;
    console.log("RECEIVED:", json);

    let parsed;
    try {
        parsed = JSON.parse(json);
        console.log("Valid JSON detected.");
    } catch (e) {
        console.log("Non‑JSON input, treating as raw text.");
        parsed = json;
    }

    // Encode both JSON credentials and string credentials as JSON. This preserves
    // the JSON string wrapper required when an SD-JWT is decoded by Verify.
    const stringified = JSON.stringify(parsed);

    const opts = {
        errorCorrectionLevel: DEFAULT_ECC_LEVEL,
        quality: DEFAULT_QR_QUALITY,
        margin: DEFAULT_QR_BORDER,
        scale: DEFAULT_QR_SCALE,
        color: {
            dark: COLOR_BLACK,
            light: COLOR_WHITE
        }
    };

    try {
        const qrData = generateQRData(stringified);
        const version = QRCode.create(qrData, { errorCorrectionLevel: DEFAULT_ECC_LEVEL }).version;

        QRCode.toDataURL(qrData, opts).then(qr => res.send([version, qr]));
    } catch (err) {
        console.error("QR generation failed:", err);
        res.status(500).send("Error generating QR");
    }
});


app.listen(port, () => {
    console.log(`Example app listening on port ${port}`)
    open('http://localhost:3000');
})

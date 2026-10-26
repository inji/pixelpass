const toQrPayload = (rawInput) => {
    const input = rawInput.trim();

    try {
        return JSON.stringify(JSON.parse(input));
    } catch (error) {
        return JSON.stringify(input);
    }
};

module.exports = {toQrPayload};

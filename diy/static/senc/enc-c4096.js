(function () {
    // Shortcuts
    var C = CryptoJS;
    var C_lib = C.lib;
    var WordArray = C_lib.WordArray;
    var C_enc = C.enc;

    /**
     * Base64 encoding strategy.
     */
    var COffset = 30000;
    var C4096 = C_enc.C4096 = {
        /**
         * Converts a word array to a Base64 string.
         *
         * @param {WordArray} wordArray The word array.
         *
         * @return {string} The Base64 string.
         *
         * @static
         *
         * @example
         *
         *     var base64String = CryptoJS.enc.Base64.stringify(wordArray);
         */
        coffset: COffset,
        
        stringify: function (wordArray) {
            // Shortcuts
            var words = wordArray.words;
            var sigBytes = wordArray.sigBytes;
            // var map = this._map;

            // Clamp excess bits
            wordArray.clamp();

            // Convert
            var base64Chars = [];
            for (var i = 0; i < sigBytes; i += 3) {
                var byte1 = (words[i >>> 2]       >>> (24 - (i % 4) * 8))       & 0xff;
                var byte2 = (words[(i + 1) >>> 2] >>> (24 - ((i + 1) % 4) * 8)) & 0xff;
                var byte3 = (words[(i + 2) >>> 2] >>> (24 - ((i + 2) % 4) * 8)) & 0xff;

                var triplet = (byte1 << 16) | (byte2 << 8) | byte3;

                for (var j = 0; (j < 4) && (i + j * 0.75 < sigBytes); j++) {
                    base64Chars.push((triplet >>> (6 * (3 - j))) & 0x3f);
                }
            }

            /*/ Add padding
            var paddingChar = 64;
            if (paddingChar) {
                while (base64Chars.length % 4) {
                    base64Chars.push(paddingChar);
                }
            }*/

            var c4096Chars = [];
            for (var i = 0; i < base64Chars.length; i += 2) {
                c4096Chars.push(String.fromCharCode(((base64Chars[i] << 6) | base64Chars[i+1]) + COffset));
            }
            if (base64Chars.length % 2 === 1) {
                c4096Chars.push(String.fromCharCode((base64Chars[i+2] << 6) + COffset + 64));
            }
            return c4096Chars.join('');
        },

        /**
         * Converts a Base64 string to a word array.
         *
         * @param {string} base64Str The Base64 string.
         *
         * @return {WordArray} The word array.
         *
         * @static
         *
         * @example
         *
         *     var wordArray = CryptoJS.enc.Base64.parse(base64String);
         */
        parse: function (base64Str) {
            // Shortcuts
            var base64StrLength = base64Str.length * 2;
            // var map = this._map;
            
            var base64Num = [];
            var char = 0, char2 = 0;
            for (var i = 0; i < base64StrLength; i += 1) {
                char = base64Str.charCodeAt(i) - COffset;
                base64Num.push(char >> 6);
                char2 = char % (1 << 6);
                if (char2 !== 64){
                    base64Num.push(char2);
                } else {
                    base64StrLength -= 1;
                }
            }

            /*/ Ignore padding
            var paddingChar = 64;
            if (paddingChar) {
                var paddingIndex = base64Num.indexOf(paddingChar);
                if (paddingIndex != -1) {
                    base64StrLength = paddingIndex;
                }
            }*/

            // Convert
            var words = [];
            var nBytes = 0;
            for (var i = 0; i < base64StrLength; i++) {
                if (i % 4) {
                    var bits1 = base64Num[i - 1] << ((i % 4) * 2);
                    var bits2 = base64Num[i] >>> (6 - (i % 4) * 2);
                    words[nBytes >>> 2] |= (bits1 | bits2) << (24 - (nBytes % 4) * 8);
                    nBytes++;
                }
            }

            return WordArray.create(words, nBytes);
        },

    };
})();

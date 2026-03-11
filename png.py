import math
import zlib


class PNG():
    
    def __init__(self):
        self.data = b''
        self.info = ''
        self.width = 0
        self.height = 0
        self.bit_depth = 0
        self.color_type = 0
        self.compress = 0
        self.filter = 0
        self.interlace = 0
        self.img = []

    def load_file(self, file_name):
        """Loads a PNG file, reads its binary content, and processes it to extract IDAT chunks."""
        try:
            with open(file_name,'rb') as file:   #rb as to open in binary mode
                self.data = file.read()
                self.info = file_name
        except FileNotFoundError:    #handles the case when the file does not exist
            self.info = 'file not found'
            raise

    def valid_png(self):
        """Validates whether the loaded file is a valid PNG by checking its signature."""
        file_signature = b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'  #Header signal for IHDR
        if self.data[0:8] == file_signature:   #check first 8 bytes for the signature
            return True
        else:
            return False
        
    def read_header(self):
        """
        Reads the IHDR chunk of the PNG file and extracts header information.
        The IHDR chunk contains essential information about the image, such as its
        dimensions, bit depth, and color type.
        """

        if self.data[12:16] == b'\x49\x48\x44\x52':  #Header signal for IHDR
            self.width = int.from_bytes(self.data[16:20], 'big') #4 bytes
            self.height = int.from_bytes(self.data[20:24], 'big') #4 bytes
            self.bit_depth = int.from_bytes(self.data[24:25]) #1 byte
            self.color_type = int.from_bytes(self.data[25:26]) #1 byte
            self.compress = int.from_bytes(self.data[26:27])  #1 byte
            self.filter = int.from_bytes(self.data[27:28])  #1 byte
            self.interlace = int.from_bytes(self.data[28:29]) #1 byte
    
    def read_chunks(self):
        """Processes the decompressed image data, applies filter types, and reconstructs the image as a 3d array"""

        # list to store data from IDAT chunks
        chunks = []
        buffer = memoryview(self.data)
        i = 8     #skip the first 8 bytes (PNG signature)
        while i + 4 < len(self.data):
            j = i + 4
            length_bytes = buffer[i:j]   #search through the file 4 bytes at a time
            if not length_bytes:
                break
            i = j
            j = i + 4
            chunk_type = buffer[i:j]
            if not chunk_type:
                break
            if chunk_type == b'IEND':  #if IEND signature is met, stop the process
                break
            length = int.from_bytes(length_bytes)
            i = j
            j = i + length
            data = buffer[i:j]
            i = j + 4   #account for crc
            if chunk_type == b'IHDR':     
                pass
            elif chunk_type == b'IDAT':
                chunks.append(data)   #only save IDAT data to empty list.
        
        idat_chunks = b''.join(chunks)   #join all IDAT chunks to a single byte object
        decompressed_data = zlib.decompress(idat_chunks)    

        bpp = 3  # bytes per pixel
        stride = self.width * bpp  # number of bytes in width
        reconstruct = []

        def _get_left(r, c):
            #returns the left pixel
            if c >= bpp:
                return reconstruct[r * stride + c - bpp]
            else:
                return 0
         
        def _get_up(r, c):
            #returns the pixel above
            if r>0 :
                return reconstruct[(r-1) * stride + c]
            else:
                return 0

        def _get_up_left(r, c):
            #returns the pixel above and to the left for Paeth
            if r > 0 and c >=bpp:
                return reconstruct[(r-1) * stride + c - bpp]
            else:
                return 0

        def _paeth(a, b, c):
            p = a + b - c
            pa = abs(p - a)
            pb = abs(p - b)
            pc = abs(p - c)
            if pa <= pb and pa <= pc:
                Pr = a
            elif pb <= pc:
                Pr = b
            else:
                Pr = c
            return Pr
        
        i = 0
        for row in range(self.height):
            filter_type = decompressed_data[i]
            i += 1
            if filter_type == 0: # None
                for col in range(stride):
                    reconstruct.append(decompressed_data[i] & 0xff)
                    i += 1
            
            elif filter_type == 1: # Sub
                for col in range(stride):
                    reconstruct.append((decompressed_data[i] + _get_left(row, col)) & 0xff)
                    i += 1
            
            elif filter_type == 2: # Up
                for col in range(stride):
                    reconstruct.append((decompressed_data[i] + _get_up(row, col)) & 0xff)
                    i += 1
            
            elif filter_type == 3: # Average
                for col in range(stride):
                    adj = (_get_left(row, col) + _get_up(row, col)) // 2
                    reconstruct.append((decompressed_data[i] + adj) & 0xff)
                    i += 1
            
            elif filter_type == 4: # Paeth
                for col in range(stride):
                    adj = _paeth(
                        _get_left(row, col),
                        _get_up(row, col),
                        _get_up_left(row, col)
                    )
                    reconstruct.append((decompressed_data[i] + adj) & 0xff)
                    i += 1
            
            else:
                raise Exception('unknown filter type')
        
        nested_list = []
        for index_a in range(0, len(reconstruct), 3):              # form [R,G,B] nested list
            nested_list.append(reconstruct[index_a:index_a + 3])

        self.img = []
        for index_b in range(0, len(nested_list), self.width):     # now form 3d array
            self.img.append(nested_list[index_b:index_b + self.width])
      
    def save_rgb(self, file_name, rgb_option):
        """Save an RGB image file in PNG format, isolating a specific RGB channel (Red, Green, or Blue)."""

        channel = rgb_option-1  #as the rgb_options start from 1
        result = []
        zero=int(0).to_bytes(1, 'big')
        
        for row in self.img:
            result.append(zero) #Filter Type 0 = add a zero to the start of each row
            for pixel in row:
                new_row = [zero]*3  # Create a new pixel row filled with zeros (3 channels: R, G, B)
                new_row[channel] = int(pixel[channel]).to_bytes(1, 'big')  # Replace the specific channel value (e.g., R, G, or B) with the byte representation

                result.extend(new_row)
        
        new_compressed = zlib.compress(bytes().join(result))
        data_length = len(new_compressed)
        
        #PNG
        png_signature = b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'  #PNG 8 byte signature
        
        #IHDR
        ihdr_length =  b'\x00\x00\x00\x0D'   
        ihdr_type = b'\x49\x48\x44\x52'
        ihdr_data = (
            self.width.to_bytes(4, 'big') +  # 4 bytes for image width
            self.height.to_bytes(4, 'big') +  # 4 bytes for image height
            b'\x08' +  # Bit depth (8 bits per channel)
            b'\x02' +  # Color type (2 = Truecolor, RGB)
            b'\x00' +  # Compression method (0 = default)
            b'\x00' +  # Filter method (0 = default)
            b'\x00'    # Interlace method (0 = no interlace)
        )    
        ihdr_crc = zlib.crc32(ihdr_type + ihdr_data).to_bytes(4, 'big')
        
        #IDAT
        idat_data = new_compressed
        idat_length = data_length.to_bytes(4, 'big')
        idat_type = b'\x49\x44\x41\x54'
        idat_crc = zlib.crc32(idat_type+new_compressed).to_bytes(4, 'big')

        #IEND
        iend_length = b'\x00\x00\x00\x00' 
        iend_type = b'\x49\x45\x4E\x44'
        iend_data = b''
        iend_crc = zlib.crc32(iend_type + iend_data).to_bytes(4, 'big')
        
        
        full_file = (
            png_signature + # PNG file signature (8 bytes)
            ihdr_length + ihdr_type + ihdr_data + ihdr_crc +  # IHDR chunk
            idat_length + idat_type + idat_data + idat_crc +  # IDAT chunk
            iend_length + iend_type + iend_data + iend_crc    # IEND chunk
        )
        
        with open(file_name, 'wb') as f:
            f.write(full_file)


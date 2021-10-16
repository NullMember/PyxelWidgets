

class RingBuffer:
    class NotEnoughSpaceException(Exception):
        def __init__(self, message):
            super().__init__(message)

    def __init__(self, length: int) -> None:
        """
        Initialize buffer

        :param length: Buffer length
        """
        self.buffer = [0] * length
        self.length = length
        self.readIndex = 0
        self.writeIndex = 0
        self.readable = 0
    
    def write(self, values: list) -> None:
        """
        Write values to buffer. If buffer is not
        big enough to write new values, it will throw
        NotEnoughSpaceException

        :param values: Values will write to buffer
        """
        if self.readable + len(values) > self.length:
            raise RingBuffer.NotEnoughSpaceException("Not enough space in buffer")
        for index, val in enumerate(values):
            self.buffer[(index + self.writeIndex) % self.length] = val
        self.readable += len(values)
        self.writeIndex = (self.writeIndex + len(values)) % self.length
    
    def read(self, length: int = 0) -> list:
        """
        Read buffer contents

        :param length: Read length. If zero or bigger than
        readable counter, it will return readable number
        of items
        """
        if length == 0 or length > self.readable:
            length = self.readable
        output = [0] * length
        for index in range(length):
            output[index] = self.buffer[(index + self.readIndex) % self.length]
        self.readable -= length
        self.readIndex = (self.readIndex + length) % self.length
        return output
    
    def reset(self) -> None:
        """
        Reset read and write index position and
        readable counter
        """
        self.writeIndex = 0
        self.readIndex = 0
        self.readable = 0

    def flush(self) -> None:
        """
        Flush buffer, reset read and write index
        position and readable counter
        """
        self.buffer = [0] * self.length
        self.reset()
    
    def debug(self) -> None:
        """
        Print debug info to console
        """
        # bit odd but works
        readable = 0
        if self.readIndex + self.readable > self.length:
            wrap = (self.readIndex + self.readable) - self.length
            wrapBackup = wrap
        else:
            wrap = 0
            wrapBackup = 0
        print(f'Buffer | {0:7d}, {1:7d}, {2:7d}, {3:7d}, {4:7d}, {5:7d}, {6:7d}, {7:7d}, {8:7d}, {9:7d}')
        print("-------------------------------------------------------------------------------------------------")
        for i in range(len(self.buffer)):
            if i == self.readIndex:
                readable = self.readable - wrapBackup
                char = "r"
            if readable <= 0:
                char = " "
            if i < wrap:
                char = "r"
            if (i % 10) == 0:
                print(f'{i:6d} | ', end = '')
                print(f'{char:1s}{self.buffer[i]:6d}', end = '')
            elif i % 10 <= 9:
                print(f', {char:1s}{self.buffer[i]:6d}', end = '')
            if (i % 10) == 9:
                print()
            readable -= 1
        print()
        print(f'Length: {self.length:6d}, ReadIndex: {self.readIndex:6d}, WriteIndex: {self.writeIndex:6d}, Readable: {self.readable:6d}')
    
    def __repr__(self) -> str:
        return f'Length: {self.length:6d}, ReadIndex: {self.readIndex:6d}, WriteIndex: {self.writeIndex:6d}, Readable: {self.readable:6d}'
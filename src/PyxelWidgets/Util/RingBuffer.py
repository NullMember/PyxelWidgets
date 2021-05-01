class NotEnoughSpaceException(Exception):
    def __init__(self, message):
        super().__init__(message)

class RingBuffer:
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
            raise NotEnoughSpaceException("Not enough space in buffer")
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
        print("{:6s} | {:7d}, {:7d}, {:7d}, {:7d}, {:7d}, {:7d}, {:7d}, {:7d}, {:7d}, {:7d}"
        .format("Buffer",  0,     1,     2,     3,     4,     5,     6,     7,     8,     9))
        print("-----------------------------------------------------------------------------------------")
        for i in range(len(self.buffer)):
            if i == self.readIndex:
                readable = self.readable - wrapBackup
                char = "r"
            if readable <= 0:
                char = " "
            if i < wrap:
                char = "r"
            if (i % 10) == 0:
                print("{:6d} | ".format(i), end = '')
                print("{:1s}{:6d}".format(char, self.buffer[i]), end = '')
            elif i % 10 <= 9:
                print(", {:1s}{:6d}".format(char, self.buffer[i]), end = '')
            if (i % 10) == 9:
                print()
            readable -= 1
        print()
        print("Length: {:6d}, ReadIndex: {:6d}, WriteIndex: {:6d}, Readable: {:6d}"
              .format(self.length, self.readIndex, self.writeIndex, self.readable))
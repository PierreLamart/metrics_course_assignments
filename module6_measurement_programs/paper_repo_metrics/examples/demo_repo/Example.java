package demo;

interface Readable {
    int getValue();
}

class Base {
    protected int value;
    public int getValue() { return value; }
}

class Example extends Base implements Readable {
    private Base peer;
    public Example(Base peer) { this.peer = peer; }
    public void setValue(int x) {
        if (x >= 0 && x < 100) {
            this.value = x;
        } else {
            this.value = 0;
        }
    }
    public int readPeer() { return peer.getValue(); }
    public int choose(int x) {
        switch (x) {
            case 1: return 10;
            case 2: return 20;
            default: return 0;
        }
    }
    public void unsupportedFlow() {
        try { peer.getValue(); } catch (RuntimeException ignored) { }
    }
}

.class public Ldemo/SmaliExample;
.super Ljava/lang/Object;

.field private value:I

.method public getValue()I
    .locals 1
    iget v0, p0, Ldemo/SmaliExample;->value:I
    return v0
.end method

.method public ping()V
    .locals 1
    invoke-virtual {p0}, Ldemo/SmaliExample;->getValue()I
    move-result v0
    if-lez v0, :done
    invoke-static {}, Ljava/net/Example;->send()V
    :done
    return-void
.end method

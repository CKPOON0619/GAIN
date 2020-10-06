import tensorflow as tf

#Generator
class myGenerator(tf.Module):
    """
    A generator class for the GAIN model.

    Args:
        Dim: Dimension of data point.
        body: A kera Model that return a matrix of the same shape as data input. 
    """
    def __init__(self,body):
        super(myGenerator,self).__init__()
        self.body = body

    def save(self,path):
        self.body.save(path)
    
    def load(self,path):
        self.body=tf.keras.models.load_model(path)

    def generate(self,x,mask):
        """
        Generator model call for GAIN which is a residual block with a dense sequential body.

        Args: 
            x: Data input scaled to have range [0,1].
            mask: mask for data. 1 = reveal, 0 = hidden

        Returns:
            Output of the generated by the generator.
        """
        masked_x=mask*x
        masked_sample=(1.-mask)*tf.random.uniform(tf.shape(x),minval=0,maxval=1,dtype=tf.float32)
        return self.body([masked_x+masked_sample,mask])


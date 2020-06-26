import tensorflow as tf
from tensorflow import Module

#Generator
## Generator loss:
def get_generator_logLoss(discriminations,mask):
    '''
    Get the logLoss contributed for generated fake values.

    Args:
        discriminations: probability predicted by discriminator that a data entry is real.
        mask:a matrix with the same size as discriminated_probs. Entry value 1 indicate a genuine value, value 0 indicate missing(generated) value.
    Returns:
        loss value contributed by generated value imagined by the generator.
    
    '''
    ## Likelinhood loss caused by discriminable values
    return -tf.reduce_sum((1-mask) * tf.math.log(discriminations + 1e-8))/tf.reduce_sum(1-mask)


def generate_random(input):
    masked_sample_x,mask=tf.split(input,num_or_size_splits=2, axis=1)
    return tf.random.uniform(tf.shape(masked_sample_x),minval=0,maxval=1,dtype=tf.float32)

def get_test_mask(x):
    '''
    Produce a test mask for the distribution of the last column.

    Args:
        x: Input data.
    Returns:
        An array of test mask with 0 at the last entries of each row and 1 in the rest of the entries.
    '''
    shape=tf.shape(x)
    testMask=tf.tile(tf.concat([tf.ones([1,shape[1]-1],dtype=tf.float32),tf.zeros([1,1],dtype=tf.float32)],axis=1),[shape[0],1])
    return testMask

def get_last_column(x):
    '''
    Collect the last column of matrx x.

    Args:
        x: Input data.
    Returns:
        All last entries of each row of x.
    '''
    return tf.gather(x,[tf.shape(x)[1]-1],axis=1)


def get_generated_value_errors(mask,hint_mask,x,generated_x):
    '''
    Get the values of the generated values that are unknown to the generator.

    Args:
        mask: a matrix with the same size as discriminated_probs. Entry value 1 indicate a genuine value, value 0 indicate missing(generated) value.
        hint_mask: mask for creating hints with 1,0 values. Same size as discriminated_probs.
        x: Input data.
        generated_x: data generated by the generator.
    Returns:
        values of the generated values that are unknown to the generator.
    '''
    ## Check the difference between generated value and actual value
    return tf.gather_nd((generated_x-x),tf.where((1-mask)*(1-hint_mask)))

def get_total_generator_truth_error(data_batch,generated_data,mask):
    '''
    Get the logLoss of generated true values.

    Args:
        x: Input data.
        generated_x: generated data by the generator.
        mask:a matrix with the same size as x. Entry value 1 indicate a genuine value, value 0 indicate missing(generated) value.
        
    Returns:
        logLoss value contributed by genuine value reconstructed by the generator.
    '''
    ## Regulating term for alteration of known truth
    return tf.reduce_sum(mask*(data_batch-generated_data)**2) / tf.reduce_sum(mask)

class myGenerator(Module):
    """
    A generator class for the GAIN model.

    Args:
        Dim: Dimension of data point.
        body: A kera Model that return a matrix of the same shape as data input. 
    """
    def __init__(self,body=generate_random):
        super(myGenerator,self).__init__()
        self.body = body

    def save(self,path):
        self.body.save(path)
    
    def load(self,path):
        self.body=tf.keras.models.load_model(path)

    def train_with_discrimination(self,data_batch,mask,hints,discriminate_fn,optimizer,alpha=1):
        '''
        The training the generator.

        Args:
            data_batch: training data.
            mask: a matrix with the same size as discriminated_probs. Entry value 1 indicate a genuine value, value 0 indicate missing(generated) value.
            hints: hints matrix for the discriminator. 1 = genuine, 0 = generated, 0.5 = unknown
            loss_fn: loss function that evaluate the loss value of generated values with input signature (x,generated_x,mask,hints,alpha).
            optimizer: optimizer used for training the discriminator.
        Returns:
            discrimination_loss: loss value for discriminator
        '''
        with tf.GradientTape(persistent=True) as tape:
            generated_data=self.generate(data_batch,mask)
            adjusted_generated_data=generated_data*(1-mask)+mask*data_batch
            discriminations=discriminate_fn(adjusted_generated_data,hints)
            # loss=get_generator_logLoss(discriminated_probs,mask)+alpha*get_generator_truth_logLoss(data_batch,generated_data,mask)
            loss=get_generator_logLoss(discriminations,mask)        
        loss_gradients = tape.gradient(loss,self.body.trainable_variables)
        optimizer.apply_gradients(zip(loss_gradients, self.body.trainable_variables))
        return loss
    
    def train_with_critic(self,data_batch,mask,hints,criticise_fn,optimizer,alpha=1):
        '''
        The training the generator.

        Args:
            data_batch: training data.
            mask: a matrix with the same size as discriminated_probs. Entry value 1 indicate a genuine value, value 0 indicate missing(generated) value.
            hints: hints matrix for the discriminator. 1 = genuine, 0 = generated, 0.5 = unknown
            loss_fn: loss function that evaluate the loss value of generated values with input signature (x,generated_x,mask,hints,alpha).
            optimizer: optimizer used for training the discriminator.
        Returns:
            discriminator_loss: loss value for discriminator
        '''
        with tf.GradientTape(persistent=True) as tape:
            generated_data=self.generate(data_batch,mask)
            adjusted_generated_data=generated_data*(1-mask)+mask*data_batch
            critics=criticise_fn(adjusted_generated_data,hints)
            critic_loss=-tf.reduce_mean(critics)      
        loss_gradients = tape.gradient(critic_loss,self.body.trainable_variables)
        optimizer.apply_gradients(zip(loss_gradients, self.body.trainable_variables))
        return critic_loss
    
    def performance_log_with_discrimination(self,writer,prefix,data_batch,mask,hints,hint_mask,discriminate_fn,epoch):  
        '''
        To be filled.
        '''    
        generatedLastCol=self.generate(data_batch,get_test_mask(data_batch))
        generated_data=self.generate(data_batch,mask)
        adjusted_generated_data=generated_data*(1-mask)+mask*data_batch
        discriminated_probs=discriminate_fn(adjusted_generated_data,hints)
        generator_loss=get_generator_logLoss(discriminated_probs,mask)
        with writer.as_default():
            tf.summary.scalar(prefix+' generator_loss', generator_loss, step=epoch) 
            tf.summary.scalar(prefix+' know value regeneration error', get_total_generator_truth_error(data_batch,generated_data,mask), step=epoch)
            tf.summary.histogram(prefix+' hidden value generation errors',get_generated_value_errors(mask,hint_mask,data_batch,generated_data), step=epoch) 
            tf.summary.histogram(prefix+' generated last column distribution',get_last_column(generatedLastCol), step=epoch) 
            tf.summary.histogram(prefix+' actual last column distribution',get_last_column(data_batch), step=epoch) 

    
    def performance_log_with_critic(self,writer,prefix,data_batch,mask,hints,hint_mask,criticise_fn,epoch):  
        '''
        To be filled.
        '''    
        generatedLastCol=self.generate(data_batch,get_test_mask(data_batch))
        generated_data=self.generate(data_batch,mask)
        adjusted_generated_data=generated_data*(1-mask)+mask*data_batch
        generated_critics_mean=tf.reduce_mean(criticise_fn(adjusted_generated_data,hints))
        genuine_critics_mean=tf.reduce_mean(criticise_fn(data_batch,hints))
        critic_loss=generated_critics_mean-genuine_critics_mean
        with writer.as_default():
            tf.summary.scalar(prefix+' know value regeneration error', get_total_generator_truth_error(data_batch,generated_data,mask), step=epoch)
            tf.summary.scalar(prefix+' critic_loss', critic_loss, step=epoch)
            tf.summary.scalar(prefix+' genuine_critics_mean',genuine_critics_mean, step=epoch) 
            tf.summary.scalar(prefix+' generated_critics_mean',generated_critics_mean, step=epoch) 
            tf.summary.histogram(prefix+' hidden value generation errors',get_generated_value_errors(mask,hint_mask,data_batch,generated_data), step=epoch) 
            tf.summary.histogram(prefix+' generated last column distribution',get_last_column(generatedLastCol), step=epoch) 
            tf.summary.histogram(prefix+' actual last column distribution',get_last_column(data_batch), step=epoch) 

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
        masked_sample=(1-mask)*tf.random.uniform(tf.shape(x),minval=0,maxval=1,dtype=tf.float32)
        return self.body(tf.concat(axis = 1, values = [masked_x+masked_sample,mask]))


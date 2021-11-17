"""
SimpSOM (Simple Self-Organizing Maps) v1.3.5
F. Comitani @2017-2021 
 
A lightweight python library for Kohonen Self-Organizing Maps (SOM).
"""

from __future__ import print_function

import sys
import numpy as np
import os, errno

import matplotlib.pyplot as plt
from matplotlib import cm
import matplotlib.patches as mpatches
from mpl_toolkits.axes_grid1 import make_axes_locatable

import simpsom.hexagons as hx
from simpsom.cluster import density_peak as dp
from simpsom.cluster import quality_threshold as qt

from sklearn.decomposition import TruncatedSVD as tsvd
from sklearn import cluster

class SOMNet:
    """ Kohonen SOM Network class. """

    def __init__(self, net_height, net_width, data, load_file=None, PCI=0, PBC=0, n_jobs=-1):

        """Initialise the SOM network.

        Args:
            net_height (int): Number of nodes along the first dimension.
            net_width (int): Numer of nodes along the second dimension.
            data (np.array or list): N-dimensional dataset.
            load_file (str, optional): Name of file to load containing information 
                to initialize the network weights.
            PCI (boolean): Activate/Deactivate Principal Component Analysis to set
                the initial value of weights
            PBC (boolean): Activate/Deactivate periodic boundary conditions,
                warning: only quality threshold clustering algorithm works with PBC.
            n_jobs (int) [WORK IN PROGRESS]: Number of parallel processes (-1 use all available)   
        """
    
        """ Switch to activate special workflow if running the colours example. """
        self.color_ex = False
        
        """ Switch to activate PCA weights initialization. """
        self.PCI = bool(PCI)

        """ Switch to activate periodic boundary conditions. """
        self.PBC = bool(PBC)

        if self.PBC == True:
            print("Periodic Boundary Conditions active.")
        else:
            print("Periodic Boundary Conditions inactive.")

        self.node_list = []
        self.data      = data.reshape(np.array([data.shape[0], data.shape[1]]))

        """ Load the weights from file, generate them randomly or from PCA. """

        if load_file == None:
            self.net_height = net_height
            self.net_width  = net_width

            min_val,max_val = [],[]
            pca_vec =[ ]

            if self.PCI == True:
                print("The weights will be initialized with PCA.")
            
                pca     = tsvd(n_components = 2)
                pca.fit(self.data)
                pca_vec = pca.components_
            
            else:
                print("The weights will be initialized randomly.")

                for i in range(self.data.shape[1]):
                    min_val.append(np.min(self.data[:,i]))
                    max_val.append(np.max(self.data[:,i]))
            
            for x in range(self.net_width):
                for y in range(self.net_height):
                    self.node_list.append(SOMNode(x,y, self.data.shape[1], \
                        self.net_height, self.net_width, self.PBC, \
                        min_val=min_val, max_val=max_val, pca_vec=pca_vec))

        else:   
            print('The weights will be loaded from file.')

            if load_file.endswith('.npy')==False:
                load_file = load_file+'.npy'
            wei_array = np.load(load_file)
            #add something to check that data and array have the same dimensions,
            #or that they are mutually exclusive
            self.net_height = int(wei_array[0][0])
            self.net_width  = int(wei_array[0][1])
            self.PBC        = bool(wei_array[0][2])

            """ Element 0 contains information on the network shape."""

            count_wei = 1
            for x in range(self.net_width):
                for y in range(self.net_height):
                    self.node_list.append(SOMNode(x,y, self.data.shape[1], 
                    self.net_height, self.net_width, self.PBC, wei_array=wei_array[count_wei]))
                    count_wei+=1

    def save(self, fileName='SOMNet_trained', out_path='./'):
    
        """Saves the network dimensions, the pbc and nodes weights to a file.

        Args:
            fileName (str, optional): Name of file where the data will be saved.
            out_path (str, optional): Path to the folder where data will be saved.
        """
        
        
        wei_array = [np.zeros(len(self.node_list[0].weights))]
        wei_array[0][0], wei_array[0][1], wei_array[0][2] = self.net_height, self.net_width, int(self.PBC)
        for node in self.node_list:
            wei_array.append(node.weights)
        np.save(os.path.join(out_path,fileName), np.asarray(wei_array))
    

    def update_sigma(self, iter):
    
        """Update the gaussian sigma.

        Args:           
            iter (int): Iteration number.
            
        """
    
        self.sigma = self.start_sigma * np.exp(-iter/self.tau)
    

    def update_learning_rate(self, iter):
    
        """Update the learning rate.

        Args:           
            iter (int): Iteration number.
            
        """
        
        self.learning_rate =  self.start_learning_rate * np.exp(-iter/self.epochs)
    

    def find_bmu(self, vec):
    
        """Find the best matching unit (BMU) for a given vector.

        Args:           
            vec (np.array): The vector to match.
            
        Returns:            
            bmu (SOMNode): The best matching unit node.
            
        """
    
        min_val = np.finfo(np.float).max
        for node in self.node_list:
            dist = node.get_distance(vec)
            if dist < min_val:
                min_val = dist
                bmu     = node
                
        return bmu  
            

    def train(self, start_learning_rate=0.01, epochs=-1):
    
        """Train the SOM.

        Args:
            start_learning_rate (float): Initial learning rate.
            epochs (int): Number of training iterations. If not selected (or -1)
                automatically set epochs as 10 times the number of datapoints
            
        """
        
        print("Training SOM... 0%", end=' ')
        self.start_sigma = max(self.net_height, self.net_width)/2
        self.start_learning_rate = start_learning_rate
        if epochs == -1:
            epochs  = self.data.shape[0]*10
        self.epochs = epochs
        self.tau    = self.epochs/np.log(self.start_sigma)
    
        #TODO:
        #Parallel(n_jobs=self.n_jobs)(delayed(my_func)(c, K, N) for c in inputs)

        for i in range(self.epochs):

            if i%100==0:
                print(("\rTraining SOM... "+str(int(i*100.0/self.epochs))+"%" ), end=' ')

            self.update_sigma(i)
            self.update_learning_rate(i)
            
            """ Train with the bootstrap-like method: 
                instead of using all the training points, a random datapoint is chosen with substitution
                for each iteration and used to update the weights of all the nodes.
            """
            
            input_vec = self.data[np.random.randint(0, self.data.shape[0]), :].reshape(np.array([self.data.shape[1]]))
            
            bmu=self.find_bmu(input_vec)
            
            for node in self.node_list:
                node.update_weights(input_vec, self.sigma, self.learning_rate, bmu)

        print("\rTraining SOM... done!")

        
    def nodes_graph(self, colnum=0, show=False, print_out=True, out_path='./', colname=None):
    
        """Plot a 2D map with hexagonal nodes and weights values

        Args:
            colnum (int): The index of the weight that will be shown as colormap.
            show (bool, optional): Choose to display the plot.
            print_out (bool, optional): Choose to save the plot to a file.
            out_path (str, optional): Path to the folder where data will be saved.
            colname (str, optional): Name of the column to be shown on the map.
        """

        if not colname:
            colname = str(colnum)

        centers = [[node.pos[0],node.pos[1]] for node in self.node_list]

        width_p=100
        dpi=72
        x_inch = self.net_width*width_p/dpi 
        y_inch = self.net_height*width_p/dpi 
        fig=plt.figure(figsize=(x_inch, y_inch), dpi=dpi)

        if self.color_ex==True:
            cols = [[np.float(node.weights[0]),np.float(node.weights[1]),np.float(node.weights[2])]for node in self.node_list]   
            ax   = hx.plot_hex(fig, centers, cols)
            ax.set_title('Node Grid w Color Features', size=80)
            print_name=os.path.join(out_path,'nodesColors.png')

        else:
            cols    = [node.weights[colnum] for node in self.node_list]
            ax      = hx.plot_hex(fig, centers, cols)
            ax.set_title('Node Grid w Feature ' +  colname, size=80)
            divider = make_axes_locatable(ax)
            cax     = divider.append_axes("right", size="5%", pad=0.0)
            cbar    = plt.colorbar(ax.collections[0], cax=cax)
            cbar.set_label(colname, size=80, labelpad=50)
            cbar.ax.tick_params(labelsize=60)

            plt.sca(ax)
            print_name = os.path.join(out_path,'nodesFeature_'+str(colnum)+'.png')
            
        if print_out == True:
            plt.savefig(print_name, bbox_inches='tight', dpi=dpi)
        if show == True:
            plt.show()
        if show != False and print_out != False:
            plt.clf()


    def diff_graph(self, show=False, print_out=True, returns=False, out_path='./'):
    
        """Plot a 2D map with nodes and weights difference among neighbouring nodes.

        Args:
            show (bool, optional): Choose to display the plot.
            print_out (bool, optional): Choose to save the plot to a file.
            returns (bool, optional): Choose to return the difference value.
            out_path (str, optional): Path to the folder where data will be saved.

        Returns:
            (list): difference value for each node.             
        """
        
        neighbours = []
        for node in self.node_list:
            node_list = []
            for nodet in self.node_list:
                if node != nodet and node.get_node_distance(nodet) <= 1.001:
                    node_list.append(nodet)
            neighbours.append(node_list)     
            
        diffs = []
        for node, neighbours in zip(self.node_list, neighbours):
            diff = 0
            for nb in neighbours:
                diff = diff+node.get_distance(nb.weights)
            diffs.append(diff)  

        centers = [[node.pos[0],node.pos[1]] for node in self.node_list]

        if show == True or print_out==True:
        
            width_p = 100
            dpi     = 72
            x_inch  = self.net_width*width_p/dpi 
            y_inch  = self.net_height*width_p/dpi 
            fig     = plt.figure(figsize=(x_inch, y_inch), dpi=dpi)

            ax = hx.plot_hex(fig, centers, diffs)
            ax.set_title('Nodes Grid w Weights Difference', size=80)
            
            divider = make_axes_locatable(ax)
            cax     = divider.append_axes("right", size="5%", pad=0.0)
            cbar    = plt.colorbar(ax.collections[0], cax=cax)
            cbar.set_label('Weights Difference', size=80, labelpad=50)
            cbar.ax.tick_params(labelsize=60)

            plt.sca(ax)
            print_name = os.path.join(out_path,'nodesDifference.png')
            
            if print_out == True:
                plt.savefig(print_name, bbox_inches='tight', dpi=dpi)
            if show == True:
                plt.show()
            if show != False and print_out != False:
                plt.clf()

        if returns == True:
            return diffs 

    def project(self, array, colnum=-1, labels=[], show=False, print_out=True, out_path='./', colname = None):

        """Project the datapoints of a given array to the 2D space of the 
            SOM by calculating the bmus. If requested plot a 2D map with as 
            implemented in nodes_graph and adds circles to the bmu
            of each datapoint in a given array.

        Args:
            array (np.array): An array containing datapoints to be mapped.
            colnum (int): The index of the weight that will be shown as colormap. 
                If not chosen, the difference map will be used instead.
            show (bool, optional): Choose to display the plot.
            print_out (bool, optional): Choose to save the plot to a file.
            out_path (str, optional): Path to the folder where data will be saved.
            colname (str, optional): Name of the column to be shown on the map.
            
        Returns:
            (list): bmu x,y position for each input array datapoint. 
            
        """
        
        if not colname:
            colname = str(colnum)

        if labels != []:
            colors  = ['#a6cee3','#1f78b4','#b2df8a','#33a02c','#fb9a99','#e31a1c',
                       '#fdbf6f','#ff7f00','#cab2d6','#6a3d9a','#ffff99','#b15928']
            counter = 0
            class_assignment = {}
            for i in range(len(labels)):
                if labels[i] not in class_assignment:
                    class_assignment[labels[i]] = colors[counter]
                    counter = (counter + 1)%len(colors)

        bmu_list,cls = [],[]
        for i in range(array.shape[0]):
            bmu_list.append(self.find_bmu(array[i,:]).pos)   
            if self.color_ex == True:
                cls.append(array[i,:])
            else: 
                if labels != []:   
                    cls.append(class_assignment[labels[i]])
                elif colnum == -1:
                    cls.append('#ffffff')
                else: 
                    cls.append(array[i,colnum])

        if show == True or print_out == True:
        
            """ Call nodes_graph/diff_graph to first build the 2D map of the nodes. """

            if self.color_ex == True:
                print_name = os.path.join(out_path,'colorProjection.png')
                self.nodes_graph(colnum, False, False)
                plt.scatter([pos[0] for pos in bmu_list],[pos[1] for pos in bmu_list], color=cls,  
                        s=500, edgecolor='#ffffff', linewidth=5, zorder=10)
                plt.title('Datapoints Projection', size=80)
            else:
                #a random perturbation is added to the points positions so that data 
                #belonging plotted to the same bmu will be visible in the plot      
                if colnum == -1:
                    print_name = os.path.join(out_path,'projection_difference.png')
                    self.diff_graph(False, False, False)
                    plt.scatter([pos[0]-0.125+np.random.rand()*0.25 for pos in bmu_list],[pos[1]-0.125+np.random.rand()*0.25 for pos in bmu_list], c=cls, cmap=cm.viridis,
                            s=400, linewidth=0, zorder=10)
                    plt.title('Datapoints Projection on Nodes Difference', size=80)
                else:   
                    print_name = os.path.join(out_path,'projection_'+ colname +'.png')
                    self.nodes_graph(colnum, False, False, colname=colname)
                    plt.scatter([pos[0]-0.125+np.random.rand()*0.25 for pos in bmu_list],[pos[1]-0.125+np.random.rand()*0.25 for pos in bmu_list], c=cls, cmap=cm.viridis,
                            s=400, edgecolor='#ffffff', linewidth=4, zorder=10)
                    plt.title('Datapoints Projection #' +  str(colnum), size=80)
                
            if labels !=[ ]:
                recs = []
                for i in class_assignment:
                    recs.append(mpatches.Rectangle((0,0),1,1,fc=class_assignment[i]))
                plt.legend(recs,class_assignment.keys(),loc=0)

            # if labels!=[]:
            #     for label, x, y in zip(labels, [pos[0] for pos in bmu_list],[pos[1] for pos in bmu_list]):
            #         plt.annotate(label, xy=(x,y), xytext=(-0.5, 0.5), textcoords='offset points', ha='right', va='bottom', size=50, zorder=11) 
            
            if print_out == True:
                plt.savefig(print_name, bbox_inches='tight', dpi=72)
            if show == True:
                plt.show()
            plt.clf()
        
        """ Print the x,y coordinates of bmus, useful for the clustering function. """
        
        return [[pos[0],pos[1]] for pos in bmu_list] 
        
        
    def cluster(self, array, clus_type='qthresh', cutoff=5, quant=0.2, percent=0.02, num_cl=8,\
                    save_file=True, file_type='dat', show=False, print_out=True, out_path='./'):
    
        """Clusters the data in a given array according to the SOM trained map.
            The clusters can also be plotted.

        Args:
            array (np.array): An array containing datapoints to be clustered.
            clus_type (str, optional): The type of clustering to be applied, so far only quality threshold (qthresh) 
                algorithm is directly implemented, other algorithms require sklearn.
            cutoff (float, optional): Cutoff for the quality threshold algorithm. This also doubles as
                maximum distance of two points to be considered in the same cluster with DBSCAN.
            percent (float, optional): The percentile that defines the reference distance in density peak clustering (dpeak).
            num_cl (int, optional): The number of clusters for K-Means clustering
            quant (float, optional): Quantile used to calculate the bandwidth of the mean shift algorithm.
            save_file (bool, optional): Choose to save the resulting clusters in a text file.
            file_type (string, optional): Format of the file where the clusters will be saved (csv or dat)
            show (bool, optional): Choose to display the plot.
            print_out (bool, optional): Choose to save the plot to a file.
            out_path (str, optional): Path to the folder where data will be saved.
            
        Returns:
            (list of int): A nested list containing the clusters with indexes of the input array points.
            
        """

        """ Call project to first find the bmu for each array datapoint, but without producing any graph. """

        bmu_list = self.project(array, show=False, print_out=False)
        clusters = []

        if clus_type == 'qthresh':
            
            """ Cluster according to the quality threshold algorithm (slow!). """
    
            clusters = qt.quality_threshold(bmu_list, cutoff, self.PBC, self.net_height, self.net_width)

        elif clus_type == 'dpeak':

            """ Cluster according to the density peak algorithm. """

            clusters = dp.density_peak(bmu_list, PBC=self.PBC, net_height=self.net_height, net_width=self.net_width)

        elif clus_type in ['MeanShift', 'DBSCAN', 'KMeans']:
        
            """ Cluster according to algorithms implemented in sklearn. """
        
            if self.PBC == True:
                print("Warning: Only Quality Threshold and Density Peak clustering work with PBC")

            try:
        
                if clus_type == 'MeanShift':
                    bandwidth = cluster.estimate_bandwidth(np.asarray(bmu_list), quantile=quant, n_samples=500)
                    cl = cluster.MeanShift(bandwidth=bandwidth, bin_seeding=True).fit(bmu_list)
                
                if clus_type == 'DBSCAN':
                    cl = cluster.DBSCAN(eps=cutoff, min_samples=5).fit(bmu_list)     
                
                if clus_type == 'KMeans':
                    cl = cluster.KMeans(n_clusters=num_cl).fit(bmu_list)

                cl_labs = cl.labels_                 
                    
                for i in np.unique(cl_labs):
                    cl_list = []
                    tmp_list = range(len(bmu_list))
                    for j,k in zip(tmp_list,cl_labs):
                        if i == k:
                            cl_list.append(j)
                    clusters.append(cl_list)     
            except:
                print(('Unexpected error: ', sys.exc_info()[0]))
                raise
        else:
            sys.exit("Error: unkown clustering algorithm " + clus_type)

        
        if save_file == True:
            with open(os.path.join(out_path,clus_type+'_clusters.'+file_type),
                      'w') as file:
                if file_type == 'csv':
                    separator = ','
                else: 
                    separator = ' '
                for line in clusters:
                    for id in line: file.write(str(id)+separator)
                    file.write('\n')
        
        if print_out==True or show==True:
            
            np.random.seed(0)
            print_name = os.path.join(out_path,clus_type+'_clusters.png')
            
            fig, ax = plt.subplots()
            
            for i in range(len(clusters)):
                randCl = "#%06x" % np.random.randint(0, 0xFFFFFF)
                xc,yc  = [],[]
                for c in clusters[i]:
                    #again, invert y and x to be consistent with the previous maps
                    xc.append(bmu_list[int(c)][0])
                    yc.append(self.net_height-bmu_list[int(c)][1])    
                ax.scatter(xc, yc, color=randCl, label='cluster'+str(i))

            plt.gca().invert_yaxis()
            plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)           
            ax.set_title('Clusters')
            ax.axis('off')

            if print_out == True:
                plt.savefig(print_name, bbox_inches='tight', dpi=600)
            if show == True:
                plt.show()
            plt.clf()   
            
        return clusters

        
class SOMNode:

    """ Single Kohonen SOM Node class. """
    
    def __init__(self, x, y, num_weights, net_height, net_width, PBC, min_val=[], max_val=[], pca_vec=[], wei_array=[]):
    
        """Initialise the SOM node.

        Args:
            x (int): Position along the first network dimension.
            y (int): Position along the second network dimension
            num_weights (int): Length of the weights vector.
            net_height (int): Network height, needed for periodic boundary conditions (PBC)
            net_width (int): Network width, needed for periodic boundary conditions (PBC)
            PBC (bool): Activate/deactivate periodic boundary conditions.
            min_val(np.array, optional): minimum values for the weights found in the data
            max_val(np.array, optional): maximum values for the weights found in the data
            pca_vec(np.array, optional): Array containing the two PCA vectors.
            wei_array (np.array, optional): Array containing the weights to give
                to the node if a file was loaded.

                
        """
    
        self.PBC     = PBC
        self.pos     = hx.coor_to_hex(x,y)
        self.weights = []

        self.net_height = net_height
        self.net_width  = net_width

        if wei_array == [] and pca_vec == []:
            #select randomly in the space spanned by the data
            for i in range(num_weights):
                self.weights.append(np.random.random()*(max_val[i]-min_val[i])+min_val[i])
        elif wei_array == [] and pca_vec != []:
            #select uniformly in the space spanned by the PCA vectors
            self.weights = (x-self.net_width/2)*2.0/self.net_width * pca_vec[0] + \
                          (y-self.net_height/2)*2.0/self.net_height *pca_vec[1]
        else:
            for i in range(num_weights):
                self.weights.append(wei_array[i])

    
    def get_distance(self, vec):
    
        """Calculate the distance between the weights vector of the node and a given vector.

        Args:
            vec (np.array): The vector from which the distance is calculated.
            
        Returns: 
            (float): The distance between the two weight vectors.
        """
    
        sum = 0
        if len(self.weights) == len(vec):
            for i in range(len(vec)):
                sum += (self.weights[i]-vec[i])*(self.weights[i]-vec[i])
            return np.sqrt(sum)
        else:
            sys.exit("Error: dimension of nodes != input data dimension!")

    def get_node_distance(self, node):
    
        """Calculate the distance within the network between the node and another node.

        Args:
            node (SOMNode): The node from which the distance is calculated.
            
        Returns:
            (float): The distance between the two nodes.
            
        """

        if self.PBC == True:

            """ Hexagonal Periodic Boundary Conditions """

            offset = 0 if self.net_height % 2 == 0 else 0.5

            return  np.min([np.sqrt((self.pos[0]-node.pos[0])*(self.pos[0]-node.pos[0])\
                                +(self.pos[1]-node.pos[1])*(self.pos[1]-node.pos[1])),
                            #right
                            np.sqrt((self.pos[0]-node.pos[0]+self.net_width)*(self.pos[0]-node.pos[0]+self.net_width)\
                                +(self.pos[1]-node.pos[1])*(self.pos[1]-node.pos[1])),
                            #bottom 
                            np.sqrt((self.pos[0]-node.pos[0]+offset)*(self.pos[0]-node.pos[0]+offset)\
                                +(self.pos[1]-node.pos[1]+self.net_height*2/np.sqrt(3)*3/4)*(self.pos[1]-node.pos[1]+self.net_height*2/np.sqrt(3)*3/4)),
                            #left
                            np.sqrt((self.pos[0]-node.pos[0]-self.net_width)*(self.pos[0]-node.pos[0]-self.net_width)\
                                +(self.pos[1]-node.pos[1])*(self.pos[1]-node.pos[1])),
                            #top 
                            np.sqrt((self.pos[0]-node.pos[0]-offset)*(self.pos[0]-node.pos[0]-offset)\
                                +(self.pos[1]-node.pos[1]-self.net_height*2/np.sqrt(3)*3/4)*(self.pos[1]-node.pos[1]-self.net_height*2/np.sqrt(3)*3/4)),
                            #bottom right
                            np.sqrt((self.pos[0]-node.pos[0]+self.net_width+offset)*(self.pos[0]-node.pos[0]+self.net_width+offset)\
                                +(self.pos[1]-node.pos[1]+self.net_height*2/np.sqrt(3)*3/4)*(self.pos[1]-node.pos[1]+self.net_height*2/np.sqrt(3)*3/4)),
                            #bottom left
                            np.sqrt((self.pos[0]-node.pos[0]-self.net_width+offset)*(self.pos[0]-node.pos[0]-self.net_width+offset)\
                                +(self.pos[1]-node.pos[1]+self.net_height*2/np.sqrt(3)*3/4)*(self.pos[1]-node.pos[1]+self.net_height*2/np.sqrt(3)*3/4)),
                            #top right
                            np.sqrt((self.pos[0]-node.pos[0]+self.net_width-offset)*(self.pos[0]-node.pos[0]+self.net_width-offset)\
                                +(self.pos[1]-node.pos[1]-self.net_height*2/np.sqrt(3)*3/4)*(self.pos[1]-node.pos[1]-self.net_height*2/np.sqrt(3)*3/4)),
                            #top left
                            np.sqrt((self.pos[0]-node.pos[0]-self.net_width-offset)*(self.pos[0]-node.pos[0]-self.net_width-offset)\
                                +(self.pos[1]-node.pos[1]-self.net_height*2/np.sqrt(3)*3/4)*(self.pos[1]-node.pos[1]-self.net_height*2/np.sqrt(3)*3/4))])
                        
        else:
            return np.sqrt((self.pos[0]-node.pos[0])*(self.pos[0]-node.pos[0])\
                +(self.pos[1]-node.pos[1])*(self.pos[1]-node.pos[1]))



    def update_weights(self, input_vec, sigma, learning_rate, bmu):
    
        """Update the node Weights.

        Args:
            input_vec (np.array): A weights vector whose distance drives the direction of the update.
            sigma (float): The updated gaussian sigma.
            learning_rate (float): The updated learning rate.
            bmu (SOMNode): The best matching unit.
        """
    
        dist  = self.get_node_distance(bmu)
        gauss = np.exp(-dist*dist/(2*sigma*sigma))

        for i in range(len(self.weights)):
            self.weights[i] = self.weights[i] - gauss*learning_rate*(self.weights[i]-input_vec[i])
        
        
if __name__ == "__main__":

    pass

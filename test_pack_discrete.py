import givenData
import numpy as np
from pct_envs.PctDiscrete0 import PackingDiscrete
from trimesh_visualizer import TrimeshPackingViewer
import time


def random(env, times = 2000):
    done = False
    episode_utilization = []
    episode_length = []
    env.reset()
    bin_size = env.bin_size

    for counter in range(times):
        while True:
            if done:
                # Reset the enviroment when the episode is done
                result = env.space.get_ratio()
                l = len(env.space.boxes)
                print('Result of episode {}, utilization: {}, length: {}'.format(counter, result, l))
                episode_utilization.append(result), episode_length.append(l)
                env.reset()
                done = False
                break

            next_box = env.next_box
            next_den = env.next_den

            # Check the feasibility of all placements.
            candidates = []
            for lx in range(bin_size[0] - next_box[0] + 1):
                for ly in range(bin_size[1] - next_box[1] + 1):
                    for rot in range(env.orientation):
                        if rot == 0:
                            x, y, z = next_box
                        elif rot == 1:
                            y, x, z = next_box
                        elif rot == 2:
                            z, x, y = next_box
                        elif rot == 3:
                            z, y, x = next_box
                        elif rot == 4:
                            x, z, y = next_box
                        elif rot == 5:
                            y, z, x = next_box

                        feasible, heightMap = env.space.drop_box_virtual([x, y, z], (lx, ly), False,
                                                                         next_den, env.setting, False, True)
                        if not feasible:
                            continue

                        candidates.append([[x, y, z], [0, lx, ly]])

            if len(candidates) != 0:
                # Pick one placement randomly from all possible placements
                idx = np.random.randint(0, len(candidates))
                viewer.show(block=False)
                time.sleep(0.5)
                env.next_box = candidates[idx][0]
                env.step(candidates[idx][1])
                done = False
            else:
                # No feasible placement, this episode is done.
                done = True

    return  np.mean(episode_utilization), np.var(episode_utilization), np.mean(episode_length)

def heightmap_min(env, times = 2000):
    done = False
    episode_utilization = []
    episode_length = []
    env.reset()
    bin_size = env.bin_size

    for counter in range(times):
        while True:
            if done:
                # Reset the enviroment when the episode is done
                result = env.space.get_ratio()
                l = len(env.space.boxes)
                print('Result of episode {}, utilization: {}, length: {}'.format(counter, result, l))
                episode_utilization.append(result), episode_length.append(l)
                env.reset()
                done = False
                break

            bestScore = 1e10
            bestAction = []

            next_box = env.next_box
            next_den = env.next_den

            for lx in range(bin_size[0] - next_box[0] + 1):
                for ly in range(bin_size[1] - next_box[1] + 1):
                    # Find the most suitable placement within the allowed orientation.
                    for rot in range(env.orientation):
                        if rot == 0:
                            x, y, z = next_box
                        elif rot == 1:
                            y, x, z = next_box
                        elif rot == 2:
                            z, x, y = next_box
                        elif rot == 3:
                            z, y, x = next_box
                        elif rot == 4:
                            x, z, y = next_box
                        elif rot == 5:
                            y, z, x = next_box

                        # Check the feasibility of this placement
                        feasible, heightMap = env.space.drop_box_virtual([x, y, z], (lx, ly), False,
                                                                             next_den, env.setting, False, True)
                        if not feasible:
                            continue

                        # Score the given placement.
                        score = lx + ly + 100 * np.sum(heightMap)
                        if score < bestScore:
                            bestScore = score
                            env.next_box = [x, y, z]
                            bestAction = [0, lx, ly]

            if len(bestAction) != 0:
                # Place this item in the environment with the best action.
                env.step(bestAction)
                viewer.show(block=False)
                time.sleep(0.5)
                done = False
            else:
                # No feasible placement, this episode is done.
                done = True

    return  np.mean(episode_utilization), np.var(episode_utilization), np.mean(episode_length)

def corner_height(env, times = 2000):
    done = False
    episode_utilization = []
    episode_length = []
    env.reset()
    bin_size = env.bin_size

    for counter in range(times):
        while True:
            if done:
                # Reset the enviroment when the episode is done
                result = env.space.get_ratio()
                l = len(env.space.boxes)
                print('Result of episode {}, utilization: {}, length: {}'.format(counter, result, l))
                episode_utilization.append(result), episode_length.append(l)
                env.reset()
                done = False
                break

            bestScore = 1e10
            bestAction = []

            next_box = env.next_box
            next_den = env.next_den

            # Get corner points of the bin
            corner_points = env.corner_positions()
            #print('Corner points:', corner_points)

            for position in corner_points:
                xs, ys, zs, xe, ye, ze = position
                x = xe - xs
                y = ye - ys
                z = ze - zs

                feasible, heightMap = env.space.drop_box_virtual([x, y, z], (xs, ys), False,next_den, env.setting, False, True)

                if not feasible:
                    continue

                # Score the given placement.
                score = xs + ys + 10 * np.sum(heightMap)
                #print(score)
                if score < bestScore:
                    bestScore = score
                    env.next_box = [x, y, z]
                    bestAction = [0, xs, ys]

            if len(bestAction) != 0:
                #print(bestScore)
                # Place this item in the environment with the best action.
                env.step(bestAction)
                #viewer.show(block=False)
                #time.sleep(0.5)
                done = False
            else:
                # No feasible placement, this episode is done.
                viewer.show(block=False)
                done = True

    return  np.mean(episode_utilization), np.var(episode_utilization), np.mean(episode_length)

def corner_height_z(env, times = 2000):
    done = False
    episode_utilization = []
    episode_length = []
    env.reset()

    for counter in range(times):
        while True:
            if done:
                # Reset the enviroment when the episode is done
                result = env.space.get_ratio()
                l = len(env.space.boxes)
                print('Result of episode {}, utilization: {}, length: {}'.format(counter, result, l))
                episode_utilization.append(result), episode_length.append(l)
                env.reset()
                done = False
                break

            bestScore = 1e10
            bestAction = []

            next_box = env.next_box
            next_den = env.next_den

            # Get corner points of the bin
            corner_points = env.corner_positions()

            scores = []
            z_heights = []
            boxes = []
            actions = []
            for position in corner_points:
                xs, ys, zs, xe, ye, ze = position
                x = xe - xs
                y = ye - ys
                z = ze - zs

                feasible, heightMap = env.space.drop_box_virtual([x, y, z], (xs, ys), False,next_den, env.setting, False, True)

                if not feasible:
                    continue

                # Score the given placement.
                score = xs + ys + 10 * np.sum(heightMap)
                scores.append(score)
                boxes.append([x, y, z])
                actions.append([0, xs, ys])
                z_heights.append(z)

            # Normalize the z heights to [0, 1]
            if len(z_heights) > 0:
                z_heights = np.array(z_heights)
                z_heights = (z_heights - np.min(z_heights)) / (np.max(z_heights) - np.min(z_heights) + 1e-5)
                # Inverse the z heights to prioritize lower placements
                z_heights = 1 - z_heights
            
            print('Z heights:', z_heights)

            # Normalize the scores to [0, 1]
            if len(scores) > 0:
                scores = np.array(scores)
                scores = (scores - np.min(scores)) / (np.max(scores) - np.min(scores) + 1e-5)
                
                # Combine scores and z heights
                combined_scores = scores + 0.5* z_heights
                print('Scores:', scores)
                print('Combined scores:', combined_scores)

                # Find highest score and corresponding box
                best_idx = np.argmin(combined_scores)
                env.next_box = boxes[best_idx]
                bestAction = actions[best_idx]

            if len(bestAction) != 0:
                #print(bestScore)
                # Place this item in the environment with the best action.
                env.step(bestAction)
                viewer.show(block=False)
                #time.sleep(0.5)
                done = False
            else:
                # No feasible placement, this episode is done.
                done = True

    return  np.mean(episode_utilization), np.var(episode_utilization), np.mean(episode_length)

if __name__ == '__main__':

    rotation = True
    setting = None
    max_packing_height = 5

    pallet_size = [10,10,max_packing_height]
    num_episodes = 1
    item_set = givenData.item_size_set

    box_data = 'box_data/discrete_sample_box_data.csv'
    load_test_data = False
    if box_data is not None and box_data != '':
        load_test_data = True
    else:
        load_test_data = False

    if rotation:
        setting = 2
    else:
        setting = 1
    

    env = PackingDiscrete(setting = setting,
                     container_size = pallet_size,
                     item_set = item_set,
                     data_name = box_data,
                     load_test_data = load_test_data,
                     internal_node_holder = 80,
                     leaf_node_holder = 1000,
                     LNES='CP')
    
    viewer = TrimeshPackingViewer(env)


    mean, var, length = corner_height(env, num_episodes)
    

    print('The average space utilization:', mean)
    print('The variance of space utilization:', var)
    print('The average number of packed items:', length)
